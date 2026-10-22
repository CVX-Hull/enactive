// Executes delimited production code. Engine rendering, JSON access and translation
// are explicit doubles, not an alternate parser or SDL/game qualification.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <deque>
#include <exception>
#include <filesystem>
#include <fcntl.h>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
namespace fs = std::filesystem;
// PRODUCTION_TYPES
std::vector<std::pair<size_t, const void *>> receivers;
const void *current_context = nullptr;
boundary_kind current_kind = boundary_kind::unsupported;
std::string session = "test", category, boundary_id, frame_name = "saved.png", pause_origin = "none";
std::vector<std::string> actions;
std::string owned_interrupt, waiting_interrupt, injected_interrupt, interrupt_session;
std::string pending, directory = ".";
int revision = 1, boundary_counter = 0, query_depth = 0, query_input_depth = -1;
int control_generation = 0, frame_revision = 1, presented_revision = 1, frame_counter = 0;
std::string frame_metadata;
std::deque<std::string> retained_frames;
long long takeover_generation = 0, clock_ms = 1000, last_poll = 0, last_publish = 0;
long long frame_ms = 1000, presented_ms = 1000;
std::string frame_boundary, frame_session = "test", presented_boundary, presented_session = "test";
bool in_game = true, paused = false, dirty = false, saved_frame_ok = true, activity_eligible = false;
std::optional<fs::file_time_type> own_pause_time;
std::set<std::string> seen_ids, control_seen_ids;
constexpr size_t control_id_limit = 4096;
long long now_ms() { return clock_ms; }
std::string path( const std::string &name ) { return name; }
void pause_file() { std::ofstream( "pause" ) << "paused"; own_pause_time = fs::last_write_time( "pause" ); }
void publish_control( const std::string &, const std::string &, const std::string & = "", bool = true, bool = false );
struct frame_geometry {
    int width = 1;
    bool operator==( const frame_geometry &other ) const { return width == other.width; }
    bool operator!=( const frame_geometry &other ) const { return !( *this == other ); }
};
std::optional<frame_geometry> saved_geometry = frame_geometry{1};
int current_width = 1, cached_width = 1;
std::optional<frame_geometry> current_frame_geometry() { return frame_geometry{current_width}; }
std::optional<frame_geometry> cached_frame_geometry() { return frame_geometry{cached_width}; }
bool reject_input_reopen = false;
struct TextJsonObject {
    std::map<std::string, std::string> strings;
    std::map<std::string, long long> integers;
    std::map<std::string, bool> booleans;
    std::map<std::string, TextJsonObject> objects;
    mutable bool omitted_members_allowed = false;
    void allow_omitted_members() const { omitted_members_allowed = true; }
    std::string get_string( const std::string &key ) const { return strings.at( key ); }
    bool get_bool( const std::string &key ) const { return booleans.at( key ); }
    TextJsonObject get_object( const std::string &key ) const {
        if( key == "input" && reject_input_reopen ) { throw std::runtime_error( "translated input reopened" ); }
        return objects.at( key );
    }
    size_t size() const { return strings.size() + integers.size() + booleans.size() + objects.size(); }
};
TextJsonObject packet;
struct TextJsonIn {
    explicit TextJsonIn( std::istream & ) {}
    TextJsonObject get_object() const { return packet; }
};
long long integer_member( const TextJsonObject &request, const std::string &key ) { return request.integers.at( key ); }
bool authority_ok = true, control_waiting = false, refuse_translation = false;
bool fail_feed = false, fail_publish = false, fail_unlink = false, encoder_ok = true;
int authority_calls = 0, feed_calls = 0;
bool partial_custody_checked = false;
std::function<void()> during_authority;
void authority_gate( const TextJsonObject &request ) {
    ++authority_calls;
    if( request.omitted_members_allowed ) { partial_custody_checked = true; }
    if( during_authority ) { during_authority(); }
    if( !authority_ok ) { throw std::runtime_error( "authority" ); }
}
std::string pixels = "original pixels";
bool write_frame( const std::string &filename ) {
    if( !encoder_ok ) { return false; }
    std::ofstream( filename ) << pixels;
    return true;
}
enum class keyboard_mode { keychar, keycode };
enum class input_event_t { keyboard_char, keyboard_code };
struct input_event { input_event_t type = input_event_t::keyboard_char; std::vector<int> sequence = {1}; };
struct direct_input {
    enum class kind { key, text, click };
    kind type = kind::key;
    input_event engine;
};
input_event key_event( const std::string &, keyboard_mode ) { return {}; }
input_event action_event( const std::string &, keyboard_mode, bool = false ) { return {}; }
direct_input direct_event( const TextJsonObject &, keyboard_mode );
struct input_manager {
    std::vector<input_event> get_input_for_action( const std::string &, const std::string & ) { return {{}}; }
} inp_mngr;
bool poll_control( keyboard_mode, input_event & ) { return control_waiting; }
std::vector<std::string> statuses;
namespace ui_manager { void redraw() {} }
void refresh_display() {
    presented_boundary = boundary_id;
    presented_session = session;
    presented_revision = revision;
    presented_ms = now_ms();
}
std::string capture_metadata( const std::optional<frame_geometry> &geometry ) {
    return "synthetic immutable metadata:" + std::to_string( geometry->width );
}
struct JsonOut { explicit JsonOut( std::ostream &stream ) : stream( stream ) {} std::ostream &stream; };
void write_observation( JsonOut &out, const std::string &id, const std::string &status,
                        const std::string &error, bool frame_ok, const std::string &frame,
                        long long stamp, const std::optional<frame_geometry> & ) {
    statuses.push_back( status );
    if( fail_publish ) { fail_publish = false; throw std::runtime_error( "publication" ); }
    if( status == "dispatched" && fail_unlink ) {
        fs::remove( "claimed.json" ); fs::create_directory( "claimed.json" ); std::ofstream( "claimed.json/child" ) << "x";
    }
    // Fixture serialization only: production publish owns all file creation,
    // capture, rename/copy and failure handling around these bytes.
    out.stream << id << '\n' << status << '\n' << error << '\n' << paused << '\n'
               << pause_origin << '\n' << frame_ok << '\n' << frame << '\n' << stamp << '\n';
}
bool publish( const std::string &, const std::string &, const std::string &, bool );
void publish_control( const std::string &id, const std::string &status, const std::string &error, bool capture, bool ) {
    publish( id, status, error, capture );
}
void feed_imgui( const input_event & ) { ++feed_calls; if( fail_feed ) { throw std::runtime_error( "widget" ); } }
void feed_direct_imgui( const direct_input &event ) { feed_imgui( event.engine ); }
// PRODUCTION_FUNCTIONS
std::function<void()> during_translation;
direct_input direct_event( const TextJsonObject &input, keyboard_mode ) {
    if( refuse_translation ) { throw input_refusal( "unsupported translation" ); }
    direct_input event;
    const std::string type = input.get_string( "type" );
    if( type == "text" ) { event.type = direct_input::kind::text; }
    else if( type == "click" ) { event.type = direct_input::kind::click; }
    else if( type != "key" ) { throw input_refusal( "unsupported input type" ); }
    // Translation has consumed this child. A commit must use its typed result,
    // rather than opening a fresh child with only a subset of members visited.
    reject_input_reopen = true;
    if( during_translation ) { during_translation(); }
    return event;
}
void require( bool value ) { if( !value ) { throw std::runtime_error( "assertion failed" ); } }
void refresh_identity() {
    frame_boundary = presented_boundary = boundary_id;
    frame_revision = presented_revision = revision;
    packet = {};
    packet.strings = {{"id", "input-1"}, {"session", session}, {"boundary_id", boundary_id},
                      {"frame", frame_name}, {"kind", "direct"}};
    packet.integers = {{"protocol", 6}, {"revision", revision}, {"takeover_generation", takeover_generation},
                       {"deadline_ms", 5000}};
    packet.booleans = {{"require_exact_frame", false}};
    packet.objects = {{"authority", {}}, {"input", {}}};
    packet.objects["input"].strings["type"] = "key";
    std::ofstream( frame_name ) << "original pixels";
}
bool refusal( const std::function<void()> &run ) {
    try { run(); } catch( const input_refusal & ) { return true; }
    return false;
}
bool hard_fault( const std::function<void()> &run ) {
    try { run(); } catch( const input_refusal & ) { throw; }
    catch( const std::runtime_error & ) { return true; }
    return false;
}
int main( int argc, char **argv ) {
    try {
        require( argc == 2 ); const std::string scenario = argv[1]; int context = 1, second = 2;
        if( scenario == "control-postcommit-feed" || scenario == "control-postcommit-publish" || scenario == "control-wire5" ) {
            scope owner( boundary_kind::activity_poll );
            scope active( "DEFAULTMODE", {"pause"}, &context ); input_receiver receiver;
            refresh_identity(); activity_eligible = true;
            packet = {};
            packet.strings = {{"id", "11111111-1111-1111-1111-111111111111"}, {"session", session}, {"kind", "request_interrupt"}};
            packet.integers = {{"protocol", scenario == "control-wire5" ? 5 : 6}, {"control_generation", control_generation},
                               {"created_ms", 1000}, {"deadline_ms", 3000}};
            packet.objects["authority"] = {};
            std::ofstream( "control.json" ) << "fixture packet";
            fail_feed = scenario == "control-postcommit-feed"; fail_publish = scenario == "control-postcommit-publish";
            input_event event; require( !production_poll_control( keyboard_mode::keychar, event ) );
            require( paused && pause_origin == "fault" );
            if( scenario == "control-wire5" ) { require( statuses == std::vector<std::string>{"rejected"} ); }
            else {
                require( std::find( statuses.begin(), statuses.end(), "rejected" ) == statuses.end() );
                require( statuses.back() == "dispatched" && waiting_interrupt.empty() && injected_interrupt.empty() );
            }
        } else if( scenario == "outside" ) {
            input_receiver receiver; require( !ordinary_receiver() );
        } else if( scenario == "normal-owner" || scenario == "unsupported-owner" || scenario == "debug" ||
                   scenario == "activity" || scenario == "interrupt" ) {
            const auto owner_kind = scenario == "normal-owner" ? boundary_kind::normal_play :
                                    scenario == "unsupported-owner" ? boundary_kind::unsupported :
                                    scenario == "debug" ? boundary_kind::debug_prompt : boundary_kind::activity_poll;
            scope owner( owner_kind );
            if( scenario == "debug" ) { require( recovery_receiver( boundary_kind::debug_prompt ) ); }
            if( scenario == "interrupt" ) { owned_interrupt = "owned"; query_depth = 1; query_input_depth = 1; }
            scope active( scenario == "interrupt" ? "YESNO" : "DEFAULTMODE", {"pause"}, &context );
            input_receiver receiver;
            require( ordinary_receiver() == ( scenario == "normal-owner" ) );
            const auto recovery_kind = scenario == "interrupt" ? boundary_kind::interrupt_confirmation : owner_kind;
            if( scenario == "activity" || scenario == "interrupt" ) { require( recovery_receiver( recovery_kind ) ); }
            {
                scope nested( scenario == "interrupt" ? "YESNO" : "HELP_UNFAMILIAR", {"escape"}, &second );
                require( !live_receiver() ); input_receiver nested_receiver;
                require( ordinary_receiver() == ( scenario == "normal-owner" ) );
                require( !recovery_receiver( recovery_kind ) );
            }
            require( live_receiver() );
        } else {
            scope active( "UNFAMILIAR", {"new action"}, &context );
            require( !ordinary_receiver() );
            {
                input_receiver receiver; require( ordinary_receiver() && current_kind == boundary_kind::menu );
                refresh_identity();
                if( scenario == "unfamiliar" ) { require( category == "UNFAMILIAR" ); }
                else if( scenario == "identity" ) {
                    const int before = revision;
                    { scope same( "UNFAMILIAR", {"new action"}, &second );
                      require( revision > before && !ordinary_receiver() ); input_receiver nested;
                      require( ordinary_receiver() ); }
                } else if( scenario == "timeouts" ) {
                    const int before = revision;
                    for( int i = 0; i < 20; ++i ) {
                        scope repeated_wait( "UNFAMILIAR", {"new action"}, &context );
                        input_receiver retry; sync_scope(); require( ordinary_receiver() );
                    }
                    require( revision == before );
                } else if( scenario == "receiver-exit" ) {
                    receivers.clear(); require( refusal( [&]() { ordinary_commit_gate( packet, false, false ); } ) );
                    receivers.emplace_back( scopes.size(), &context );
                } else if( scenario == "receiver-changed-at-commit" ) {
                    during_authority = [&]() { if( authority_calls == 2 ) { receivers.back().second = &second; } };
                    require( refusal( [&]() { ordinary_commit_gate( packet, false, false ); } ) );
                } else if( scenario == "direct-key-resize" || scenario == "direct-text-resize" ) {
                    current_width = cached_width = 2; pixels = "changed by f(T)";
                    if( scenario == "direct-text-resize" ) { packet.objects["input"].strings["type"] = "text"; }
                    ordinary_commit_gate( packet, false, false );
                } else if( scenario == "direct-click-resize" ) {
                    packet.objects["input"].strings["type"] = "click"; current_width = 2;
                    require( refusal( [&]() { ordinary_commit_gate( packet, false, true ); } ) );
                } else if( scenario == "direct-exact-rejected" ) {
                    packet.booleans["require_exact_frame"] = true;
                    require( refusal( [&]() { ordinary_commit_gate( packet, false, false ); } ) );
                } else if( scenario == "direct-key-stale-frame" || scenario == "direct-text-stale-frame" ||
                           scenario == "direct-click-stale-frame" ) {
                    if( scenario == "direct-text-stale-frame" ) { packet.objects["input"].strings["type"] = "text"; }
                    if( scenario == "direct-click-stale-frame" ) { packet.objects["input"].strings["type"] = "click"; }
                    packet.strings["frame"] = "frame-original-capture.png";
                    require( refusal( [&]() { ordinary_commit_gate( packet, false,
                                             scenario == "direct-click-stale-frame" ); } ) );
                } else if( scenario == "semantic-exact" || scenario == "semantic-drift" || scenario == "comparison-io" || scenario == "comparison-symlink" ) {
                    packet.strings["kind"] = "key"; packet.booleans["require_exact_frame"] = true;
                    if( scenario == "semantic-drift" ) { pixels = "different bytes"; }
                    if( scenario == "comparison-io" ) { fs::remove( frame_name ); }
                    if( scenario == "comparison-symlink" ) { fs::remove( frame_name ); fs::create_symlink( "missing", frame_name ); }
                    if( scenario == "semantic-drift" ) { require( refusal( [&]() { ordinary_commit_gate( packet, false, false ); } ) ); }
                    else if( scenario != "semantic-exact" ) { require( hard_fault( [&]() { ordinary_commit_gate( packet, false, false ); } ) ); }
                    else { ordinary_commit_gate( packet, false, false ); }
                    require( !fs::exists( "frame.compare.tmp.png" ) );
                } else if( scenario == "stale" ) {
                    ++revision; require( refusal( [&]() { ordinary_commit_gate( packet, false, false ); } ) );
                } else if( scenario == "authority" || scenario == "pause" ) {
                    if( scenario == "authority" ) { authority_ok = false; } else { paused = true; }
                    require( hard_fault( [&]() { ordinary_commit_gate( packet, false, false ); } ) );
                } else {
                    std::ofstream( "request.json" ) << "fixture packet";
                    if( scenario == "expected-refusal" || scenario == "refusal-capture-failure" ||
                        scenario == "refusal-capture-human" || scenario == "refusal-storage-failure" ) {
                        refuse_translation = true;
                        if( scenario == "refusal-storage-failure" ) { fs::create_directory( "response.json.tmp" ); }
                        else if( scenario != "expected-refusal" ) { encoder_ok = false; }
                    }
                    else if( scenario == "hard-fault" || scenario == "human-fault" ) { authority_ok = false; }
                    else if( scenario == "wire5" ) { packet.integers["protocol"] = 5; }
                    else if( scenario == "postcommit-feed" ) { fail_feed = true; }
                    else if( scenario == "postcommit-publish" ) { fail_publish = true; }
                    else if( scenario == "postcommit-unlink" ) { fail_unlink = true; }
                    else if( scenario == "control-first" ) { control_waiting = true; }
                    else if( scenario == "translated-key" || scenario == "translated-text" ||
                             scenario == "translated-click" || scenario == "translated-click-resize" ) {
                        packet.objects["input"].strings["type"] = scenario == "translated-key" ? "key" :
                                scenario == "translated-text" ? "text" : "click";
                        if( scenario != "translated-click" ) {
                            during_translation = []() { current_width = cached_width = 2; pixels = "changed by f(T)"; };
                        }
                    }
                    else { throw std::runtime_error( "unknown scenario" ); }
                    if( scenario == "human-fault" || scenario == "refusal-capture-human" ) { pause_origin = "human"; }
                    input_event event; const bool delivered = poll( keyboard_mode::keychar, event );
                    if( scenario == "control-first" ) { require( delivered && feed_calls == 0 && fs::exists( "request.json" ) ); }
                    else if( scenario == "translated-key" || scenario == "translated-text" || scenario == "translated-click" ) {
                        require( delivered && feed_calls == 1 && pending == "input-1" );
                        require( !partial_custody_checked && !paused && !fs::exists( "pause" ) &&
                                 statuses == std::vector<std::string>{"dispatched"} );
                    }
                    else if( scenario == "expected-refusal" || scenario == "translated-click-resize" ) {
                        require( !delivered && !paused && pause_origin == "none" && !fs::exists( "pause" ) );
                        require( partial_custody_checked && feed_calls == 0 &&
                                 statuses == std::vector<std::string>{"rejected"} );
                    } else {
                        require( !delivered && paused && fs::exists( "pause" ) );
                        require( pause_origin == ( scenario == "human-fault" || scenario == "refusal-capture-human" ? "human" : "fault" ) );
                        if( scenario == "refusal-capture-failure" || scenario == "refusal-capture-human" ) {
                            require( feed_calls == 0 && !saved_frame_ok );
                            std::ifstream response( "response.json" );
                            const std::string bytes{ std::istreambuf_iterator<char>( response ), std::istreambuf_iterator<char>() };
                            require( bytes.find( "input-1\nrejected\n" ) == 0 );
                            require( bytes.find( "\n1\n" + pause_origin + "\n0\n" ) != std::string::npos );
                        }
                        if( scenario == "refusal-storage-failure" ) {
                            require( feed_calls == 0 && !fs::exists( "response.json" ) );
                        }
                        if( scenario.find( "postcommit" ) == 0 ) {
                            require( std::find( statuses.begin(), statuses.end(), "rejected" ) == statuses.end() );
                            require( statuses.back() == "dispatched" );
                        } else if( scenario != "refusal-storage-failure" ) { require( statuses.back() == "rejected" ); }
                    }
                }
            }
            require( !ordinary_receiver() );
        }
        std::cout << scenario << " passed\n";
    } catch( const std::exception &error ) { std::cerr << error.what() << '\n'; return 1; }
}
