#include "cdda_harness.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <exception>
#include <fcntl.h>
#include <fstream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <cctype>
#include <stdexcept>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

#include "avatar.h"
#include "calendar.h"
#include "catacharset.h"
#include "game.h"
#include "input.h"
#include "input_context.h"
#include "options.h"
#include "json.h"
#include "map.h"
#include "mapdata.h"
#include "output.h"
#include "sdltiles.h"
#include "ui_manager.h"
#include "third-party/imgui/imgui.h"

namespace cdda_harness
{
namespace
{
namespace fs = std::filesystem;
long long now_ms()
{
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::system_clock::now().time_since_epoch() ).count();
}
const std::string directory = []() {
    const char *value = std::getenv( "CDDA_HARNESS_DIR" );
    std::error_code error;
    struct stat info = {};
    if( !value || !fs::is_directory( value, error ) || stat( value, &info ) != 0 ||
        ( info.st_mode & 0077 ) != 0 ) {
        return std::string();
    }
    // Held for the lifetime of the game; a second producer must not share files.
    const int lock = open( ( std::string( value ) + "/game.lock" ).c_str(), O_CREAT | O_RDWR, 0600 );
    if( lock < 0 || flock( lock, LOCK_EX | LOCK_NB ) != 0 ) {
        if( lock >= 0 ) {
            close( lock );
        }
        std::fprintf( stderr, "CDDA harness disabled: another game owns the bridge\n" );
        return std::string();
    }
    return std::string( value );
}();
std::string session = std::to_string( now_ms() ) + "-" + std::to_string( getpid() );
std::string category;
std::vector<std::string> actions;
std::string pending;
std::set<std::string> seen_ids;
std::set<std::string> control_seen_ids;
constexpr size_t control_id_limit = 4096;
std::string injected_interrupt;
std::string owned_interrupt;
std::string interrupt_session;
std::string waiting_interrupt;
bool activity_eligible = false;
int owner_depth = 0;
int query_depth = 0;
int query_input_depth = -1;
int revision = 0;
// Process lifetime: neither session replacement nor recovery clears human input.
long long takeover_generation = 0;
std::string pause_origin = "startup";
int last_turn = -1;
bool dirty = true;
struct input_scope {
    boundary_kind kind;
    std::string category;
    std::vector<std::string> actions;
    bool input;
    const void *context = nullptr;
    bool recovery = false;
};
std::vector<input_scope> scopes;
std::vector<std::pair<size_t, const void *>> receivers;
const void *current_context = nullptr;
boundary_kind current_kind = boundary_kind::unsupported;
int boundary_counter = 0;
int control_generation = 0;
int world_counter = 0;
std::string boundary_id;
std::string presented_boundary;
std::string presented_session;
int presented_revision = -1;
long long presented_ms = 0;

std::string kind_name( boundary_kind kind )
{
    switch( kind ) {
        case boundary_kind::normal_play: return "normal_play";
        case boundary_kind::activity_poll: return "activity_poll";
        case boundary_kind::interrupt_confirmation: return "interrupt_confirmation";
        case boundary_kind::debug_prompt: return "debug_prompt";
        case boundary_kind::menu: return "menu";
        default: return "unsupported";
    }
}
bool scoped()
{
    return !scopes.empty() && ( scopes.back().input ||
                               scopes.back().kind == boundary_kind::debug_prompt );
}
// Receiver lifetime is deliberately absent from boundary identity: timeout retries
// in the same context do not advance revision or renew the saved frame clock.
bool live_receiver()
{
    return !receivers.empty() && !scopes.empty() && scopes.back().input && scopes.back().context != nullptr &&
           receivers.back().first == scopes.size() &&
           receivers.back().second == scopes.back().context;
}
bool ordinary_receiver()
{
    return live_receiver() && ( scopes.back().kind == boundary_kind::normal_play ||
                               scopes.back().kind == boundary_kind::menu );
}
bool recovery_receiver( boundary_kind kind )
{
    return !scopes.empty() && scopes.back().kind == kind && scopes.back().recovery &&
           ( !scopes.back().input || live_receiver() );
}
class input_refusal : public std::runtime_error
{
    public:
        using std::runtime_error::runtime_error;
};
void new_boundary()
{
    boundary_id = session + "-b" + std::to_string( ++boundary_counter );
    ++revision;
    dirty = true;
}
void sync_scope()
{
    const input_scope empty = { boundary_kind::unsupported, "", {}, false };
    const input_scope &top = scopes.empty() ? empty : scopes.back();
    const boundary_kind effective = top.kind == boundary_kind::interrupt_confirmation && owned_interrupt.empty() ?
                                    boundary_kind::menu : top.kind;
    if( current_kind != effective || current_context != top.context ||
        category != top.category || actions != top.actions ||
        boundary_id.empty() ) {
        current_kind = effective;
        current_context = top.context;
        category = top.category;
        actions = top.actions;
        new_boundary();
    }
}
bool in_game = false;
bool paused = true;
tripoint_abs_ms origin;
long long last_poll = 0;
long long last_publish = 0;
int frame_counter = 0;
std::string frame_name;
std::string frame_boundary;
std::string frame_session;
std::string frame_metadata;
int frame_revision = -1;
long long frame_ms = 0;
bool saved_frame_ok = false;
std::optional<frame_geometry> saved_geometry;
std::optional<fs::file_time_type> own_pause_time;
struct visible_row {
    std::string text;
    bool enabled;
    std::string hotkey;
    bool selected;
};
struct visible_ui {
    std::string purpose;
    std::string category;
    std::string title;
    std::vector<visible_row> rows;
};
bool ui_top = false;
std::optional<visible_ui> staged_ui;
std::string presented_ui;
std::optional<visible_ui> presented_ui_data;
std::string ui_boundary;
std::string ui_session;
int ui_revision = -1;

// Conservatively bound UTF-8 bytes without cutting a codepoint. Schema limits
// count characters, so this tighter bound also meets the public contract.
std::string ui_text( const std::string &text, size_t maximum )
{
    size_t length = std::min( text.size(), maximum );
    while( length < text.size() && length > 0 &&
           ( static_cast<unsigned char>( text[length] ) & 0xc0 ) == 0x80 ) {
        --length;
    }
    return text.substr( 0, length );
}
void write_ui( JsonOut &out, const visible_ui &ui )
{
    out.start_object();
    out.member( "purpose", ui.purpose );
    out.member( "title", ui.title );
    out.member( "rows" );
    out.start_array();
    std::string selected;
    for( size_t i = 0; i < ui.rows.size(); ++i ) {
        const visible_row &row = ui.rows[i];
        const std::string id = "row-" + std::to_string( i );
        out.start_object();
        out.member( "id", id );
        out.member( "text", row.text );
        out.member( "enabled", row.enabled );
        out.member( "hotkey" );
        if( row.hotkey.empty() ) { out.write_null(); }
        else { out.write( row.hotkey ); }
        out.end_object();
        if( row.selected ) { selected = id; }
    }
    out.end_array();
    out.member( "selected" );
    if( selected.empty() ) { out.write_null(); }
    else { out.write( selected ); }
    // These separately drawn fields have no clipping/occlusion attestation yet.
    out.member( "filter" ); out.write_null();
    out.member( "count" ); out.write_null();
    out.member( "coverage", "rendered_rows_only" );
    out.end_object();
}
std::string encode_ui( const visible_ui &ui )
{
    std::ostringstream stream;
    JsonOut out( stream );
    write_ui( out, ui );
    return stream.str();
}
// Retention preserves the issued source and clock across later render-only churn.
struct issued_capture {
    std::string name;
    long long timestamp_ms;
    std::string metadata;
};
std::deque<issued_capture> retained_frames;

std::string path( const std::string &name )
{
    return directory + "/" + name;
}
void pause_file()
{
    std::ofstream out( path( "pause" ) );
    out.exceptions( std::ios::badbit | std::ios::failbit );
    out << "paused\n";
    out.close();
    own_pause_time = fs::last_write_time( path( "pause" ) );
}
void fault_pause()
{
    paused = true;
    if( pause_origin != "human" ) { pause_origin = "fault"; }
    pause_file();
}
void scene( JsonOut &out )
{
    out.member( "scene" );
    if( !in_game || current_kind != boundary_kind::normal_play ) {
        out.write_null();
        return;
    }
    const avatar &u = get_avatar();
    map &here = get_map();
    const auto pos = u.pos_bub( here );
    const auto delta = u.pos_abs() - origin;
    out.start_object();
    out.member( "provenance", "player-visible input boundary" );
    out.member( "position", std::vector<int> { delta.x(), delta.y(), delta.z() } );
    out.member( "turn", to_turn<int>( calendar::turn ) );
    // Use the UI's own visible-creature list, including its perception rules.
    out.member( "visible_creatures" );
    out.start_array();
    for( const Creature *creature : u.get_visible_creatures( 60 ) ) {
        out.start_object();
        out.member( "name", creature->disp_name() );
        out.member( "hostile", u.attitude_to( *creature ) == Creature::Attitude::HOSTILE );
        out.end_object();
    }
    out.end_array();
    out.member( "neighbors" );
    out.start_array();
    const auto &cache = here.get_visibility_variables_cache();
    for( int dy = -1; dy <= 1; ++dy ) {
        for( int dx = -1; dx <= 1; ++dx ) {
            if( dx == 0 && dy == 0 ) {
                continue;
            }
            const tripoint_bub_ms tile = pos + point( dx, dy );
            const bool visible = here.inbounds( tile ) &&
                                 here.get_visibility( here.apparent_light_at( tile, cache ), cache ) == visibility_type::CLEAR;
            out.start_object();
            out.member( "dx", dx );
            out.member( "dy", dy );
            out.member( "visible", visible );
            if( visible ) {
                out.member( "terrain", here.ter( tile ).id().str() );
                out.member( "name", here.tername( tile ) );
                out.member( "furniture", here.furn( tile ).id().str() );
            }
            out.end_object();
        }
    }
    out.end_array();
    out.end_object();
}
void write_observation( JsonOut &out, const std::string &id, const std::string &status,
                        const std::string &error, bool frame_ok, const std::string &published_frame,
                        long long capture_ms, const std::optional<frame_geometry> &geometry )
{
    out.start_object();
    out.member( "protocol", 6 );
    out.member( "id", id );
    out.member( "session", session );
    out.member( "revision", revision );
    out.member( "category", category );
    out.member( "actions", actions );
    out.member( "status", status );
    out.member( "error", error );
    out.member( "paused", paused );
    out.member( "pause_origin", pause_origin );
    out.member( "takeover_generation", takeover_generation );
    out.member( "ui" );
    if( frame_ok && !presented_ui.empty() &&
        ui_boundary == boundary_id && ui_session == session && ui_revision == revision ) {
        // Serialized by encode_ui, never arbitrary request data.
        write_ui( out, *presented_ui_data );
    } else {
        out.write_null();
    }
    out.member( "timestamp_ms", frame_ok ? capture_ms : now_ms() );
    out.member( "frame_ok", frame_ok );
    out.member( "frame", published_frame );
    out.member( "frame_geometry" );
    if( frame_ok && geometry ) {
        out.start_object();
        out.member( "window_width", geometry->window_width );
        out.member( "window_height", geometry->window_height );
        out.member( "output_width", geometry->output_width );
        out.member( "output_height", geometry->output_height );
        out.member( "viewport", geometry->viewport );
        out.end_object();
    } else {
        out.write_null();
    }
    out.member( "boundary" );
    out.start_object();
    out.member( "kind", kind_name( current_kind ) );
    out.member( "id", boundary_id );
    out.member( "control_generation", control_generation );
    out.member( "input_receiver", ordinary_receiver() );
    std::vector<std::string> operations;
    if( recovery_receiver( boundary_kind::activity_poll ) && activity_eligible ) {
        operations.push_back( "request_interrupt" );
    } else if( recovery_receiver( boundary_kind::interrupt_confirmation ) && !owned_interrupt.empty() ) {
        operations.push_back( "answer_interrupt" );
    } else if( recovery_receiver( boundary_kind::debug_prompt ) ) {
        operations.push_back( "continue_debug_once" );
    }
    out.member( "recovery_operations", operations );
    out.member( "interrupt_request_id" );
    if( recovery_receiver( boundary_kind::interrupt_confirmation ) && !owned_interrupt.empty() ) {
        out.write( owned_interrupt );
    } else {
        out.write_null();
    }
    out.end_object();
    out.member( "in_game", in_game );
    scene( out );
    out.end_object();
}
bool same_frame_png( const std::string &saved, const std::string &latest, const struct stat &owned );
std::string capture_metadata( const std::optional<frame_geometry> &geometry )
{
    // Normalize only capture/transport identity. Reuse the complete observation
    // serializer so new immutable fields cannot silently escape this comparison.
    std::ostringstream stream;
    JsonOut out( stream );
    write_observation( out, "", "", "", true, "capture", 0, geometry );
    return stream.str();
}
bool publish( const std::string &id, const std::string &status,
              const std::string &error = "", bool capture = true )
{
    bool frame_ok = false;
    std::string published_frame;
    if( capture ) {
        const bool previous_valid = saved_frame_ok;
        saved_frame_ok = false;
        saved_geometry.reset();
        // Present and copy this boundary's current render buffer. A cached front
        // buffer from an earlier prompt must never acquire a new timestamp.
        ui_manager::redraw();
        refresh_display();
        frame_ok = presented_boundary == boundary_id && presented_session == session &&
                   presented_revision == revision;
        if( frame_ok && !write_frame( path( "frame.tmp.png" ) ) ) {
            throw std::runtime_error( "attempted frame capture encoding or storage failed" );
        }
        if( frame_ok ) {
            const auto geometry = cached_frame_geometry();
            const std::string metadata = capture_metadata( geometry );
            struct stat candidate = {};
            const bool same_capture = id.empty() && previous_valid && !frame_name.empty() &&
                                      frame_metadata == metadata &&
                                      lstat( path( "frame.tmp.png" ).c_str(), &candidate ) == 0 &&
                                      same_frame_png( path( frame_name ), path( "frame.tmp.png" ), candidate );
            // Compare before checking age: encoding and filesystem I/O can be
            // slow. Neither a heartbeat nor equal pixels renew the original TTL.
            const long long checked_ms = now_ms();
            const bool reuse = same_capture && checked_ms >= frame_ms && checked_ms - frame_ms < 3000;
            if( reuse ) {
                fs::remove( path( "frame.tmp.png" ) );
            } else {
                frame_name = "frame-" + session + "-" + std::to_string( ++frame_counter ) + ".png";
                fs::rename( path( "frame.tmp.png" ), path( frame_name ) );
                fs::copy_file( path( frame_name ), path( "frame.latest.png" ), fs::copy_options::overwrite_existing );
                fs::rename( path( "frame.latest.png" ), path( "frame.png" ) );
                frame_ms = presented_ms;
                frame_metadata = metadata;
                retained_frames.push_back( { frame_name, frame_ms, metadata } );
                if( retained_frames.size() > 120 ) {
                    std::error_code ignored;
                    fs::remove( path( retained_frames.front().name ), ignored );
                    retained_frames.pop_front();
                }
            }
            published_frame = frame_name;
            frame_boundary = boundary_id;
            frame_session = session;
            frame_revision = revision;
            saved_frame_ok = true;
            saved_geometry = geometry;
        }
    }
    const std::string output = id.empty() ? "state.json" : "response.json";
    std::ofstream stream( path( output + ".tmp" ) );
    stream.exceptions( std::ios::badbit | std::ios::failbit );
    JsonOut out( stream );
    write_observation( out, id, status, error, frame_ok, published_frame, frame_ms, saved_geometry );
    stream.close();
    fs::rename( path( output + ".tmp" ), path( output ) );
    if( !id.empty() ) {
        fs::copy_file( path( output ), path( "state.json.tmp" ), fs::copy_options::overwrite_existing );
        fs::rename( path( "state.json.tmp" ), path( "state.json" ) );
    }
    dirty = false;
    last_publish = now_ms();
    return frame_ok;
}
void publish_control( const std::string &id, const std::string &status,
                      const std::string &error = "", bool capture = true, bool prepared = false )
{
    if( !prepared ) { publish( "", "ready", "", capture ); }
    // Snapshot bytes are already produced by our exact observation serializer.
    // Serialize all envelope strings before embedding that same JSON object.
    std::ifstream snapshot( path( "state.json" ) );
    std::ofstream stream( path( "control-response.json.tmp" ) );
    stream.exceptions( std::ios::badbit | std::ios::failbit );
    stream << "{\"protocol\":6,\"id\":";
    { JsonOut out( stream ); out.write( id ); }
    stream << ",\"status\":";
    { JsonOut out( stream ); out.write( status ); }
    stream << ",\"error\":";
    { JsonOut out( stream ); out.write( error ); }
    stream << ",\"state\":" << snapshot.rdbuf() << "}";
    stream.close();
    fs::rename( path( "control-response.json.tmp" ), path( "control-response.json" ) );
}
input_event key_event( const std::string &key, keyboard_mode mode )
{
    const bool chars = mode == keyboard_mode::keychar;
    const std::map<std::string, std::pair<int, int>> special = {
        { "ENTER", { '\n', keycode::return_ } }, { "ESC", { KEY_ESCAPE, keycode::escape } },
        { "UP", { KEY_UP, keycode::up } }, { "DOWN", { KEY_DOWN, keycode::down } },
        { "LEFT", { KEY_LEFT, keycode::left } }, { "RIGHT", { KEY_RIGHT, keycode::right } },
        { "TAB", { '\t', keycode::tab } }, { "BACKSPACE", { KEY_BACKSPACE, keycode::backspace } },
        { "SPACE", { ' ', keycode::space } }, { "PAGEUP", { KEY_PPAGE, keycode::ppage } },
        { "PAGEDOWN", { KEY_NPAGE, keycode::npage } }
    };
    const auto found = special.find( key );
    input_event result;
    result.type = chars ? input_event_t::keyboard_char : input_event_t::keyboard_code;
    if( found != special.end() ) {
        result.sequence.push_back( chars ? found->second.first : found->second.second );
        if( key == "SPACE" ) {
            result.text = " ";
        }
    } else if( key.size() == 1 && key[0] >= 32 && key[0] <= 126 ) {
        int code = key[0];
        result.text = key;
        if( !chars && code >= 'A' && code <= 'Z' ) {
            code += 'a' - 'A';
            result.modifiers.insert( keymod_t::shift );
        } else if( !chars ) {
            const std::string shifted = "~!@#$%^&*()_+{}|:\"<>?";
            const std::string base = "`1234567890-=[]\\;',./";
            const auto index = shifted.find( static_cast<char>( code ) );
            if( index != std::string::npos ) {
                code = base[index];
                result.modifiers.insert( keymod_t::shift );
            }
        }
        result.sequence.push_back( code );
    } else {
        throw input_refusal( "key must be one ASCII character or supported named key" );
    }
    return result;
}
long long integer_member( const TextJsonObject &object, const std::string &name )
{
    TextJsonIn *raw = object.get_raw( name );
    raw->eat_whitespace();
    const int begin = raw->tell();
    const int64_t value = raw->get_int64();
    const int end = raw->tell();
    // Upstream accepts scientific notation as an integer. The wire contract
    // requires an integer JSON literal, matching the host's strict int check.
    for( int offset = begin; offset < end; ++offset ) {
        raw->seek( offset );
        const char ch = raw->peek();
        if( ch == ',' || ch == '}' || ch == ']' || std::isspace( static_cast<unsigned char>( ch ) ) ) {
            break;
        }
        if( !( ch >= '0' && ch <= '9' ) && !( offset == begin && ch == '-' ) ) {
            throw std::runtime_error( "integer literal required: " + name );
        }
    }
    raw->seek( end );
    return value;
}
// Read again at commit, after binding resolution; claiming a request grants no authority.
void authority_gate( const TextJsonObject &request )
{
    if( !fs::exists( path( "authority.json" ) ) || fs::file_size( path( "authority.json" ) ) > 4096 ) {
        throw std::runtime_error( "missing or oversized host authority" );
    }
    const TextJsonObject admitted = request.get_object( "authority" );
    std::ifstream stream( path( "authority.json" ) );
    TextJsonIn input( stream );
    const TextJsonObject live = input.get_object();
    const std::string boot = admitted.get_string( "controller_boot_id" );
    const long long counter = integer_member( admitted, "counter" );
    if( admitted.size() != 2 || live.size() != 2 || boot.empty() || counter < 0 ||
        live.get_string( "controller_boot_id" ) != boot || integer_member( live, "counter" ) != counter ) {
        throw std::runtime_error( "host authority revoked or malformed" );
    }
}
void ordinary_gate( const TextJsonObject &request, bool require_current_frame = false )
{
    authority_gate( request );
    if( integer_member( request, "takeover_generation" ) != takeover_generation ) {
        throw std::runtime_error( "human generation changed" );
    }
    if( request.get_string( "session" ) != session ) { throw std::runtime_error( "session changed" ); }
    if( integer_member( request, "revision" ) != revision ) {
        throw input_refusal( "revision changed; observe again" );
    }
    if( request.get_string( "boundary_id" ) != boundary_id ) {
        throw input_refusal( "boundary changed; observe again" );
    }
    if( !saved_frame_ok ) { throw std::runtime_error( "capture is unhealthy" ); }
    const std::string source = request.get_string( "frame" );
    const auto issued = std::find_if( retained_frames.begin(), retained_frames.end(),
    [&source]( const issued_capture &capture ) { return capture.name == source; } );
    if( issued == retained_frames.end() ) {
        throw input_refusal( "capture was not issued or is no longer retained" );
    }
    if( require_current_frame && source != frame_name ) {
        throw input_refusal( "action requires the current capture" );
    }
    if( frame_name.empty() || frame_boundary != boundary_id || frame_session != session ||
        frame_revision != revision ) {
        throw input_refusal( "saved capture context changed" );
    }
    if( presented_boundary != boundary_id || presented_session != session || presented_revision != revision ) {
        throw input_refusal( "presented render context changed" );
    }
    if( issued->metadata != capture_metadata( cached_frame_geometry() ) ) {
        throw input_refusal( "capture observation metadata changed" );
    }
    // Serialization work cannot renew or outrun the original source clocks.
    const long long checked_ms = now_ms();
    if( checked_ms < issued->timestamp_ms || checked_ms - issued->timestamp_ms > 3000 ) {
        throw input_refusal( "original capture expired or clock moved backwards" );
    }
    if( checked_ms < frame_ms || checked_ms - frame_ms > 3000 ) {
        throw input_refusal( "current saved capture expired or clock moved backwards" );
    }
    if( checked_ms < presented_ms || checked_ms - presented_ms > 3000 ) {
        throw input_refusal( "presented render expired or clock moved backwards" );
    }
    if( integer_member( request, "deadline_ms" ) < now_ms() ) {
        throw input_refusal( "request deadline expired" );
    }
}
bool same_frame_png( const std::string &saved, const std::string &latest, const struct stat &owned )
{
    constexpr off_t maximum_frame_bytes = 32 * 1024 * 1024;
    const int saved_fd = open( saved.c_str(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK );
    const int latest_fd = open( latest.c_str(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK );
    struct stat saved_info = {};
    struct stat latest_info = {};
    bool healthy = saved_fd >= 0 && latest_fd >= 0 &&
                   fstat( saved_fd, &saved_info ) == 0 && fstat( latest_fd, &latest_info ) == 0 &&
                   S_ISREG( saved_info.st_mode ) && S_ISREG( latest_info.st_mode ) &&
                   saved_info.st_size > 0 && saved_info.st_size <= maximum_frame_bytes &&
                   latest_info.st_size > 0 && latest_info.st_size <= maximum_frame_bytes &&
                   latest_info.st_dev == owned.st_dev && latest_info.st_ino == owned.st_ino;
    bool same = saved_info.st_size == latest_info.st_size;
    std::array<char, 32 * 1024> saved_chunk;
    std::array<char, 32 * 1024> latest_chunk;
    off_t remaining = saved_info.st_size;
    while( healthy && same && remaining > 0 ) {
        const off_t amount = std::min( remaining, static_cast<off_t>( saved_chunk.size() ) );
        const ssize_t saved_read = read( saved_fd, saved_chunk.data(), static_cast<size_t>( amount ) );
        const ssize_t latest_read = read( latest_fd, latest_chunk.data(), static_cast<size_t>( amount ) );
        healthy = saved_read == amount && latest_read == amount;
        same = healthy && std::equal( saved_chunk.begin(), saved_chunk.begin() + amount, latest_chunk.begin() );
        remaining -= amount;
    }
    // A real byte/length difference is ordinary drift. Unreadable, substituted,
    // truncated or growing files are integrity/I/O faults, never harmless drift.
    if( healthy && same ) {
        char trailing;
        healthy = read( saved_fd, &trailing, 1 ) == 0 && read( latest_fd, &trailing, 1 ) == 0;
    }
    if( saved_fd >= 0 && close( saved_fd ) != 0 ) { healthy = false; }
    if( latest_fd >= 0 && close( latest_fd ) != 0 ) { healthy = false; }
    if( !healthy ) { throw std::runtime_error( "frame comparison integrity or I/O failure" ); }
    return same;
}
void exact_frame_gate()
{
    // Compare the cached presented surface; do not redraw or renew its clock.
    const std::string saved = path( frame_name );
    const std::string latest = path( "frame.compare.tmp.png" );
    const int descriptor = open( latest.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600 );
    if( descriptor < 0 ) {
        throw std::runtime_error( "cannot exclusively create exact frame temporary file" );
    }
    struct stat owned = {};
    const bool identified = fstat( descriptor, &owned ) == 0;
    struct stat current = {};
    bool same = false;
    std::exception_ptr failure;
    try {
        if( !identified || lstat( latest.c_str(), &current ) != 0 ||
            current.st_dev != owned.st_dev || current.st_ino != owned.st_ino || !write_frame( latest ) ) {
            throw std::runtime_error( "exact frame capture integrity or I/O failure" );
        }
        same = same_frame_png( saved, latest, owned );
    } catch( ... ) { failure = std::current_exception(); }
    const bool closed = close( descriptor ) == 0;
    const bool removed = identified && lstat( latest.c_str(), &current ) == 0 &&
                         current.st_dev == owned.st_dev && current.st_ino == owned.st_ino &&
                         unlink( latest.c_str() ) == 0;
    if( !removed || !closed ) {
        throw std::runtime_error( "exact frame temporary file cleanup failed" );
    }
    if( failure ) { std::rethrow_exception( failure ); }
    if( !same ) { throw input_refusal( "latest presented PNG changed" ); }
}
void ordinary_commit_gate( const TextJsonObject &request, bool resuming, bool click )
{
    // Click classification comes from the already-consumed primary direct-event parse.
    const bool require_current_frame = click || request.get_bool( "require_exact_frame" );
    ordinary_gate( request, require_current_frame );
    if( !ordinary_receiver() ) { throw input_refusal( "no live ordinary input receiver" ); }
    if( !resuming && ( paused || fs::exists( path( "pause" ) ) ) ) {
        throw std::runtime_error( "pause interrupted dispatch" );
    }
    if( request.get_string( "kind" ) == "direct" && request.get_bool( "require_exact_frame" ) ) {
        throw input_refusal( "direct input requires physical-event preflight" );
    }
    if( click &&
        ( !saved_geometry || current_frame_geometry() != saved_geometry ||
          cached_frame_geometry() != saved_geometry ) ) {
        throw input_refusal( "direct input requires unchanged attested frame geometry" );
    }
    if( request.get_bool( "require_exact_frame" ) ) {
        exact_frame_gate();
    }
    // The encoder/comparison can be slow. No game-thread input processing or
    // redraw interleaves it; queued physical input is handled by CheckMessages.
    // Host Pause still revokes the durable authority token, including Resume,
    // whose existing sentinel is intentionally consumed only after this gate.
    ordinary_gate( request, require_current_frame );
    if( !ordinary_receiver() ) { throw input_refusal( "no live ordinary input receiver" ); }
    if( !waiting_interrupt.empty() || fs::exists( path( "control.json" ) ) ||
        fs::exists( path( "control-claimed.json" ) ) ) {
        throw std::runtime_error( "recovery is pending" );
    }
    if( integer_member( request, "deadline_ms" ) < now_ms() ) {
        throw input_refusal( "request expired before input commit" );
    }
    if( !resuming && ( paused || fs::exists( path( "pause" ) ) ) ) {
        throw std::runtime_error( "pause interrupted dispatch" );
    }
    // A window size/scale change during PNG comparison must also refuse before
    // committing the already-translated input, even without a processed event.
    if( click && current_frame_geometry() != saved_geometry ) {
        throw input_refusal( "frame geometry changed before input commit" );
    }
}
input_event action_event( const std::string &action, keyboard_mode mode, bool confirmation = false )
{
    if( std::find( actions.begin(), actions.end(), action ) == actions.end() ) {
        throw input_refusal( "recovery action not registered" );
    }
    const auto &bindings = inp_mngr.get_input_for_action( action, category );
    const auto type = mode == keyboard_mode::keychar ? input_event_t::keyboard_char : input_event_t::keyboard_code;
    const auto binding = std::find_if( bindings.begin(), bindings.end(), [type, confirmation]( const input_event & candidate ) {
        return candidate.type == type && candidate.sequence.size() == 1 &&
               ( !confirmation || !get_option<bool>( "FORCE_CAPITAL_YN" ) ||
                 input_context::disallow_lower_case_or_non_modified_letters( candidate ) );
    } );
    if( binding == bindings.end() ) {
        throw input_refusal( "recovery action has no usable single-key binding" );
    }
    return *binding;
}
// The host additionally checks Unicode printability categories. Native checks
// canonical UTF-8 and scalar/control structure without locale or Unicode tables.
int single_printable_scalar( const std::string &text )
{
    if( text.empty() || text.size() > 4 ) {
        throw input_refusal( "text must be one printable Unicode scalar" );
    }
    const uint32_t code = UTF8_getch( text );
    if( code > 0x10ffff || ( code >= 0xd800 && code <= 0xdfff ) ||
        code < 32 || ( code >= 127 && code <= 159 ) || code == 0x2028 || code == 0x2029 ||
        utf32_to_utf8( code ) != text ) {
        throw input_refusal( "text must be one canonical noncontrol Unicode scalar" );
    }
    // The pinned widget build uses ImWchar16. Refuse before dispatch instead
    // of allowing its UTF-8 decoder to silently substitute U+FFFD.
    if( code > IM_UNICODE_CODEPOINT_MAX ) {
        throw input_refusal( "Unicode scalar exceeds the pinned widget range" );
    }
    return static_cast<int>( code );
}
std::optional<frame_geometry> input_geometry( const TextJsonObject &input )
{
    const TextJsonObject geometry = input.get_object( "geometry" );
    if( geometry.size() != 5 || !geometry.has_array( "viewport" ) ) {
        throw input_refusal( "unsupported frame geometry" );
    }
    frame_geometry result;
    const auto dimension = [&]( const std::string &name ) {
        const long long value = integer_member( geometry, name );
        if( value <= 0 || value > 16384 ) { throw input_refusal( "invalid geometry dimension" ); }
        return static_cast<int>( value );
    };
    result.window_width = dimension( "window_width" );
    result.window_height = dimension( "window_height" );
    result.output_width = dimension( "output_width" );
    result.output_height = dimension( "output_height" );
    if( static_cast<long long>( result.output_width ) * result.output_height > 16777216 ) {
        throw input_refusal( "frame pixel limit exceeded" );
    }
    TextJsonArray viewport = geometry.get_array( "viewport" );
    if( viewport.size() != 4 ) { throw input_refusal( "invalid viewport" ); }
    // Validate raw tokens as integer literals; upstream's integer reader alone
    // also accepts scientific notation, which this wire contract rejects.
    TextJsonIn *raw = geometry.get_raw( "viewport" );
    raw->start_array();
    for( size_t index = 0; index < 4; ++index ) {
        raw->eat_whitespace();
        const int begin = raw->tell();
        const int64_t number = raw->get_int64();
        const int end = raw->tell();
        for( int offset = begin; offset < end; ++offset ) {
            raw->seek( offset );
            const char ch = raw->peek();
            if( ch == ',' || ch == ']' || std::isspace( static_cast<unsigned char>( ch ) ) ) { break; }
            if( ch < '0' || ch > '9' ) { throw input_refusal( "viewport requires nonnegative integer literals" ); }
        }
        raw->seek( end );
        if( number < 0 || number > 16384 ) { throw input_refusal( "invalid viewport coordinate" ); }
        result.viewport[index] = static_cast<int>( number );
    }
    if( !raw->end_array() ) { throw input_refusal( "invalid viewport length" ); }
    if( result.viewport[2] <= 0 || result.viewport[3] <= 0 ||
        result.viewport[0] + result.viewport[2] > result.output_width ||
        result.viewport[1] + result.viewport[3] > result.output_height ) {
        throw input_refusal( "viewport outside output" );
    }
    return result;
}
direct_input direct_event( const TextJsonObject &input, keyboard_mode mode )
{
    direct_input event;
    const std::string type = input.get_string( "type" );
    if( type == "key" ) {
        if( input.size() != 3 || !input.has_array( "modifiers" ) ) {
            throw input_refusal( "unsupported direct key shape" );
        }
        const std::string key = input.get_string( "key" );
        // key_event is pure; unlike SDL's keychar translator it never reads
        // held physical keys or touches arrow-combination state.
        event.engine = key_event( key, keyboard_mode::keycode );
        TextJsonArray modifiers = input.get_array( "modifiers" );
        if( modifiers.size() > 3 ) { throw input_refusal( "too many key modifiers" ); }
        std::set<keymod_t> explicit_modifiers;
        for( const std::string modifier : modifiers ) {
            keymod_t parsed;
            if( modifier == "CTRL" ) { parsed = keymod_t::ctrl; }
            else if( modifier == "ALT" ) { parsed = keymod_t::alt; }
            else if( modifier == "SHIFT" ) { parsed = keymod_t::shift; }
            else { throw input_refusal( "unsupported key modifier" ); }
            if( !explicit_modifiers.insert( parsed ).second ) {
                throw input_refusal( "duplicate key modifier" );
            }
        }
        for( keymod_t modifier : explicit_modifiers ) {
            event.engine.modifiers.insert( modifier );
        }
        event.widget_key = event.engine.get_first_input();
        event.widget_modifiers = event.engine.modifiers;
        const bool ctrl = event.engine.modifiers.count( keymod_t::ctrl );
        const bool alt = event.engine.modifiers.count( keymod_t::alt );
        const bool shift = event.engine.modifiers.count( keymod_t::shift );
        const bool printable = ( key.size() == 1 && key[0] >= 32 && key[0] <= 126 ) || key == "SPACE";
        int glyph = event.widget_key;
        if( printable && shift ) {
            const std::string base = "`1234567890-=[]\\;',./";
            const std::string shifted = "~!@#$%^&*()_+{}|:\"<>?";
            const auto index = base.find( static_cast<char>( glyph ) );
            if( glyph >= 'a' && glyph <= 'z' ) { glyph -= 'a' - 'A'; }
            else if( index != std::string::npos ) { glyph = shifted[index]; }
        }
        if( printable && !ctrl && !alt ) { event.widget_text = std::string( 1, static_cast<char>( glyph ) ); }
        if( mode == keyboard_mode::keychar ) {
            const bool arrow = key == "UP" || key == "DOWN" || key == "LEFT" || key == "RIGHT";
            if( alt || ( arrow && ( ctrl || shift ) ) ||
                ( ctrl && ( event.widget_key < 'a' || event.widget_key > 'z' ) ) ||
                ( shift && !printable && key != "TAB" ) ) {
                throw input_refusal( "unsupported keychar modifier combination" );
            }
            event.engine = key_event( key, mode );
            event.engine.text = event.widget_text;
            if( ctrl ) { event.engine.sequence[0] = event.widget_key - 'a' + 1; }
            else if( printable ) { event.engine.sequence[0] = glyph; }
            else if( shift && key == "TAB" ) { event.engine.sequence[0] = KEY_BTAB; }
        } else {
            event.engine.text = event.widget_text;
        }
    } else if( type == "text" ) {
        if( input.size() != 2 ) { throw input_refusal( "unsupported direct text shape" ); }
        const std::string text = input.get_string( "text" );
        const int code = single_printable_scalar( text );
        event.type = direct_input::kind::text;
        event.engine = input_event( code, input_event_t::keyboard_char );
        event.engine.text = text;
        event.widget_text = text;
    } else if( type == "click" ) {
        if( input.size() != 5 ) { throw input_refusal( "unsupported direct click shape" ); }
        const std::string button = input.get_string( "button" );
        if( button != "left" && button != "right" ) { throw input_refusal( "unsupported click button" ); }
        const auto geometry = input_geometry( input );
        const long long x = integer_member( input, "x" );
        const long long y = integer_member( input, "y" );
        if( !geometry || geometry != saved_geometry || x < 0 || y < 0 ||
            x >= geometry->output_width || y >= geometry->output_height ) {
            throw input_refusal( "click requires matching geometry and an in-frame pixel" );
        }
        event.type = direct_input::kind::click;
        event.right_button = button == "right";
        event.engine = input_event( event.right_button ? MouseInput::RightButtonReleased : MouseInput::LeftButtonReleased,
                                    input_event_t::mouse );
        event.engine.mouse_pos = point( static_cast<int>( x * geometry->window_width / geometry->output_width ),
                                       static_cast<int>( y * geometry->window_height / geometry->output_height ) );
        event.widget_position = point( static_cast<int>( x ), static_cast<int>( y ) );
    } else {
        throw input_refusal( "unsupported direct input type" );
    }
    return event;
}
bool uuid_id( const std::string &id )
{
    if( id.size() != 36 ) {
        return false;
    }
    for( size_t index = 0; index < id.size(); ++index ) {
        if( index == 8 || index == 13 || index == 18 || index == 23 ) {
            if( id[index] != '-' ) { return false; }
        } else if( !( id[index] >= '0' && id[index] <= '9' ) && !( id[index] >= 'a' && id[index] <= 'f' ) ) {
            return false;
        }
    }
    return true;
}
bool poll_control( keyboard_mode mode, input_event &event )
{
    if( !fs::exists( path( "control.json" ) ) ) {
        return false;
    }
    std::error_code claim_error;
    // Never overwrite evidence from an unresolved claim.
    if( fs::exists( path( "control-claimed.json" ) ) ) {
        return false;
    }
    fs::rename( path( "control.json" ), path( "control-claimed.json" ), claim_error );
    if( claim_error ) { return false; }
    std::string id;
    bool input_committed = false;
    try {
        if( fs::file_size( path( "control-claimed.json" ) ) > 4096 ) {
            throw std::runtime_error( "control exceeds 4096 bytes" );
        }
        std::ifstream stream( path( "control-claimed.json" ) );
        TextJsonIn input( stream );
        const TextJsonObject request = input.get_object();
        id = request.get_string( "id" );
        if( !uuid_id( id ) || control_seen_ids.size() >= control_id_limit ||
            !control_seen_ids.insert( id ).second ) {
            throw std::runtime_error( "invalid, duplicate or exhausted control identity" );
        }
        const std::string kind = request.get_string( "kind" );
        size_t fields = 8;
        if( kind == "answer_interrupt" ) { fields += 5; }
        else if( kind == "continue_debug_once" ) { fields += 3; }
        else if( kind != "request_interrupt" ) { throw std::runtime_error( "unsupported control kind" ); }
        const long long created = integer_member( request, "created_ms" );
        const long long deadline = integer_member( request, "deadline_ms" );
        if( request.size() != fields || integer_member( request, "protocol" ) != 6 ||
            created < 0 || created > now_ms() + 1000 || deadline != created + 2000 || deadline < now_ms() ) {
            throw std::runtime_error( "unsupported control envelope or expired request" );
        }
        if( request.get_string( "session" ) != session ||
            integer_member( request, "control_generation" ) != control_generation ) {
            throw std::runtime_error( "stale control session or generation" );
        }
        authority_gate( request );
        if( kind == "request_interrupt" ) {
            if( !recovery_receiver( boundary_kind::activity_poll ) || !activity_eligible ) {
                publish_control( id, "not_applicable" );
                fs::remove( path( "control-claimed.json" ) );
                return false;
            }
            if( !saved_frame_ok || frame_boundary != boundary_id || frame_session != session ||
                frame_revision != revision || now_ms() - frame_ms > 3000 ) {
                throw std::runtime_error( "interrupt requires a fresh rendered activity boundary" );
            }
            event = action_event( "pause", mode );
        } else {
            if( request.get_string( "boundary_id" ) != boundary_id || integer_member( request, "revision" ) != revision ||
                request.get_string( "frame" ) != frame_name || frame_name.empty() || !saved_frame_ok ||
                frame_boundary != boundary_id || frame_session != session || frame_revision != revision ||
                now_ms() - frame_ms > 3000 ||
                presented_boundary != boundary_id || presented_session != session ||
                presented_revision != revision || now_ms() - presented_ms > 3000 ) {
                throw std::runtime_error( "stale recovery prompt or frame" );
            }
            if( kind == "answer_interrupt" ) {
                const std::string choice = request.get_string( "choice" );
                if( !recovery_receiver( boundary_kind::interrupt_confirmation ) || owned_interrupt.empty() ||
                    request.get_string( "interrupt_request_id" ) != owned_interrupt ||
                    ( choice != "YES" && choice != "NO" ) ) {
                    throw std::runtime_error( "control does not own this confirmation" );
                }
                event = action_event( choice, mode, true );
            } else {
                if( !recovery_receiver( boundary_kind::debug_prompt ) ) {
                    throw std::runtime_error( "debug continuation requires raw debug boundary" );
                }
                event = key_event( "SPACE", mode );
            }
        }
        paused = true;
        pause_origin = "recovery";
        pause_file();
        // This is the sole recovery commit gate. A Pause after this cannot undo input.
        authority_gate( request );
        if( deadline < now_ms() ) {
            throw std::runtime_error( "control expired before input commit" );
        }
        if( !saved_frame_ok || frame_boundary != boundary_id || frame_session != session ||
            frame_revision != revision || now_ms() - frame_ms > 3000 ||
            ( kind != "request_interrupt" && ( presented_boundary != boundary_id ||
                    presented_session != session || presented_revision != revision ||
                    now_ms() - presented_ms > 3000 ) ) ) {
            throw std::runtime_error( "recovery frame expired before input commit" );
        }
        const boundary_kind receiver_kind = kind == "request_interrupt" ? boundary_kind::activity_poll :
                                            kind == "answer_interrupt" ? boundary_kind::interrupt_confirmation :
                                            boundary_kind::debug_prompt;
        if( !recovery_receiver( receiver_kind ) ) {
            throw std::runtime_error( "recovery receiver changed before input commit" );
        }
        ++control_generation;
        ++revision;
        dirty = true;
        input_committed = true;
        if( kind == "request_interrupt" ) {
            injected_interrupt = id;
            interrupt_session = session;
            waiting_interrupt = id;
            publish_control( id, "dispatched", "", false );
        } else {
            publish_control( id, kind == "answer_interrupt" ? "answer_delivered" : "dismissal_delivered", "", false );
        }
        fs::remove( path( "control-claimed.json" ) );
        feed_imgui( event );
        return true;
    } catch( const std::exception &error ) {
        event = input_event();
        fault_pause();
        if( input_committed ) {
            // Preserve uncertainty after any committed publication/feed failure.
            // Do not let a later query manufacture a ready receipt for this input.
            waiting_interrupt.clear();
            injected_interrupt.clear();
            try { publish_control( id, "dispatched", error.what(), false ); }
            catch( const std::exception &publication_error ) {
                std::ofstream( path( "bridge-error.txt" ) ) << publication_error.what();
            }
            return false;
        }
        // Malformed/unidentified claims remain evidence and block subsequent recovery.
        if( !id.empty() ) {
            try {
                publish_control( id, "rejected", error.what() );
                fs::remove( path( "control-claimed.json" ) );
            } catch( const std::exception &publication_error ) {
                std::ofstream( path( "bridge-error.txt" ) ) << publication_error.what();
            }
        }
        return false;
    }
}
} // namespace

void ui_redraw( bool top )
{
    // Every callback clears the lower window, including unsupported overlays.
    ui_top = top;
    staged_ui.reset();
}
void ui_begin( const std::string &purpose, const std::string &category, const std::string &title )
{
    if( !enabled() || !ui_top ) { return; }
    staged_ui = visible_ui { ui_text( purpose, 128 ), category, ui_text( title, 1024 ), {} };
}
void ui_row( const std::string &text, bool enabled, const std::string &hotkey, bool selected )
{
    if( !ui_top || !staged_ui || staged_ui->rows.size() >= 32 ) { return; }
    staged_ui->rows.push_back( { ui_text( text, 1024 ), enabled, ui_text( hotkey, 32 ), selected } );
}

bool enabled()
{
    return !directory.empty();
}

scope::scope( boundary_kind kind )
{
    scopes.push_back( { kind, kind == boundary_kind::debug_prompt ? "DEBUG_MSG" : "", {}, false,
                       nullptr, kind == boundary_kind::debug_prompt } );
    if( kind == boundary_kind::debug_prompt ) {
        sync_scope();
        new_boundary();
    }
}
scope::scope( const std::string &name, const std::vector<std::string> &registered,
              const void *context )
{
    boundary_kind kind = boundary_kind::menu;
    bool recovery = false;
    // A context name never establishes authority. Explicit restricted owners
    // propagate their prohibition through every nested context.
    for( const input_scope &entry : scopes ) {
        if( entry.kind == boundary_kind::unsupported || entry.kind == boundary_kind::debug_prompt ||
            entry.kind == boundary_kind::activity_poll || entry.kind == boundary_kind::interrupt_confirmation ) {
            kind = entry.kind;
            break;
        }
    }
    if( kind == boundary_kind::menu && !scopes.empty() && !scopes.back().input &&
        scopes.back().kind == boundary_kind::normal_play && name == "DEFAULTMODE" && in_game ) {
        kind = boundary_kind::normal_play;
    }
    // Restrictions inherit; recovery permissions do not. Only the pinned direct
    // owner's input depth, or exact cancellation query, may receive recovery.
    if( query_depth > 0 && !owned_interrupt.empty() && name == "YESNO" &&
        static_cast<int>( scopes.size() ) == query_input_depth &&
        kind != boundary_kind::unsupported && kind != boundary_kind::debug_prompt ) {
        kind = boundary_kind::interrupt_confirmation;
        recovery = true;
    } else if( kind == boundary_kind::activity_poll && !scopes.empty() &&
               !scopes.back().input && scopes.back().kind == boundary_kind::activity_poll &&
               name == "DEFAULTMODE" ) {
        recovery = true;
    }
    scopes.push_back( { kind, name, registered, true, context, recovery } );
    sync_scope();
}
input_receiver::input_receiver()
{
    receivers.emplace_back( scopes.size(), !scopes.empty() && scopes.back().input ?
                            scopes.back().context : nullptr );
}
input_receiver::~input_receiver()
{
    receivers.pop_back();
}
scope::~scope()
{
    if( !scopes.back().input && scopes.back().kind == boundary_kind::debug_prompt ) {
        new_boundary();
    }
    if( !scopes.back().input && scopes.back().kind == boundary_kind::activity_poll ) {
        activity_eligible = false;
        // The engine may map no pause, finish, or decline to enter cancellation.
        // Never leave a dispatched interrupt owning a later activity invocation.
        if( !waiting_interrupt.empty() ) {
            try { publish_control( waiting_interrupt, "not_applicable" ); }
            catch( const std::exception &error ) {
                std::ofstream( path( "bridge-error.txt" ) ) << error.what();
            }
        }
        waiting_interrupt.clear();
        injected_interrupt.clear();
    }
    scopes.pop_back();
    // Restoration is lazy until rendering/input: repeated timeout polls in the
    // same context keep their identity, while a nested observed UI changes it.
}
void activity_interruptible( bool value )
{
    activity_eligible = value;
}
interrupt_owner::interrupt_owner()
{
    ++owner_depth;
    // The pause already passed its durable commit gate. Later revocation cannot
    // undo that engine input; every answer has its own newer admission/token.
    if( owner_depth == 1 && interrupt_session == session ) {
        owned_interrupt = injected_interrupt;
        injected_interrupt.clear();
    }
}
interrupt_owner::~interrupt_owner()
{
    if( --owner_depth == 0 ) {
        if( !waiting_interrupt.empty() ) {
            try { publish_control( waiting_interrupt, "not_applicable" ); }
            catch( const std::exception &error ) {
                std::ofstream( path( "bridge-error.txt" ) ) << error.what();
            }
        }
        waiting_interrupt.clear();
        owned_interrupt.clear();
        injected_interrupt.clear();
        new_boundary();
    }
}
interrupt_query::interrupt_query() : active( owner_depth > 0 && !owned_interrupt.empty() )
{
    if( active ) {
        ++query_depth;
        query_input_depth = static_cast<int>( scopes.size() );
        new_boundary();
    }
}
interrupt_query::~interrupt_query()
{
    if( active ) {
        --query_depth;
        query_input_depth = -1;
        new_boundary();
    }
}
void playing( bool value )
{
    if( in_game == value ) {
        return;
    }
    in_game = value;
    session = std::to_string( now_ms() ) + "-" + std::to_string( getpid() ) +
              "-" + std::to_string( ++world_counter );
    paused = true;
    if( pause_origin != "human" ) { pause_origin = "world_change"; }
    ++control_generation;
    staged_ui.reset();
    new_boundary();
    last_turn = -1;
    seen_ids.clear();
    injected_interrupt.clear();
    owned_interrupt.clear();
    waiting_interrupt.clear();
    activity_eligible = false;
    // Do not acknowledge an action from a world that no longer exists.
    pending.clear();
    if( !directory.empty() ) {
        pause_file();
        if( value ) {
            origin = get_avatar().pos_abs();
        }
    }
}
void frame_presented( bool valid )
{
    if( !valid || !scoped() ) {
        presented_boundary.clear();
        staged_ui.reset();
        presented_ui.clear();
        presented_ui_data.reset();
        return;
    }
    sync_scope();
    const int turn = in_game ? to_turn<int>( calendar::turn ) : -1;
    if( turn != last_turn ) {
        last_turn = turn;
        ++revision;
        dirty = true;
    }
    const bool supported_ui = staged_ui && current_kind == boundary_kind::menu &&
                              staged_ui->category == category;
    const std::string next_ui = supported_ui ? encode_ui( *staged_ui ) : "";
    if( next_ui != presented_ui ) {
        // Same context and turn can display changed labels, filtering or selection.
        new_boundary();
    }
    presented_ui = next_ui;
    presented_ui_data = supported_ui ? staged_ui : std::nullopt;
    staged_ui.reset(); // A cached buffer cannot attest rows for a later presentation.
    ui_top = false;
    ui_boundary = boundary_id;
    ui_session = session;
    ui_revision = revision;
    presented_boundary = boundary_id;
    presented_session = session;
    presented_revision = revision;
    presented_ms = now_ms();
}
void human_input()
{
    if( directory.empty() ) {
        return;
    }
    paused = true;
    pause_origin = "human";
    ++takeover_generation;
    injected_interrupt.clear();
    owned_interrupt.clear();
    waiting_interrupt.clear();
    ++control_generation;
    new_boundary();
    pause_file();
}
void boundary()
{
    if( directory.empty() || !scoped() ) {
        return;
    }
    try {
        sync_scope();
        const int turn = in_game ? to_turn<int>( calendar::turn ) : -1;
        if( turn != last_turn ) {
            last_turn = turn;
            ++revision;
            dirty = true;
        }
        if( !waiting_interrupt.empty() && recovery_receiver( boundary_kind::interrupt_confirmation ) &&
            !owned_interrupt.empty() ) {
            if( publish( "", "ready" ) ) {
                publish_control( waiting_interrupt, "prompt_opened", "", false, true );
                waiting_interrupt.clear();
            }
        }
        if( !pending.empty() ) {
            publish( pending, "ready" );
            pending.clear();
        } else if( dirty ) {
            publish( "", "ready" );
        }
    } catch( const std::exception &e ) {
        fault_pause();
        std::ofstream( path( "bridge-error.txt" ) ) << e.what();
    }
}
bool poll( keyboard_mode mode, input_event &event )
{
    if( directory.empty() || !scoped() || now_ms() - last_poll < 25 ) {
        return false;
    }
    last_poll = now_ms();
    std::string id;
    bool input_committed = false;
    try {
        if( fs::exists( path( "pause" ) ) &&
            ( !paused || !own_pause_time || fs::last_write_time( path( "pause" ) ) != *own_pause_time ) ) {
            paused = true;
            pause_origin = "host";
            own_pause_time = fs::last_write_time( path( "pause" ) );
            // Host Pause revokes its durable token but changes no game input or
            // rendered scene. Advancing revision here invalidates the capture
            // needed by the recovery request admitted under the new token.
            // Actual input, turn, boundary and takeover changes still advance it.
            dirty = true;
        }
        try {
            if( poll_control( mode, event ) ) {
                return true;
            }
        } catch( const std::exception &error ) {
            fault_pause();
            std::ofstream( path( "bridge-error.txt" ) ) << error.what();
            return false;
        }
        if( !pending.empty() ) {
            return false;
        }
        if( !fs::exists( path( "request.json" ) ) ) {
            if( dirty || now_ms() - last_publish >= 1000 ) {
                publish( "", "ready" );
            }
            return false;
        }
        // Atomic claim races safely with host retirement: only one rename wins.
        std::error_code claim_error;
        fs::rename( path( "request.json" ), path( "claimed.json" ), claim_error );
        if( claim_error ) {
            return false;
        }
        if( fs::file_size( path( "claimed.json" ) ) > 4096 ) {
            throw std::runtime_error( "request exceeds 4096 bytes" );
        }
        std::ifstream stream( path( "claimed.json" ) );
        TextJsonIn input( stream );
        const TextJsonObject request = input.get_object();
        id = request.get_string( "id" );
        if( id.empty() || id.size() > 80 || !seen_ids.insert( id ).second ) {
            throw std::runtime_error( "invalid or duplicate request id" );
        }
        if( integer_member( request, "protocol" ) != 6 ) {
            throw std::runtime_error( "unsupported protocol" );
        }
        const std::string kind = request.get_string( "kind" );
        if( integer_member( request, "deadline_ms" ) < now_ms() ) {
            throw std::runtime_error( "expired request" );
        }
        const size_t fields = kind == "observe" || kind == "pause" ? 4 : kind == "resume" ? 11 : 12;
        if( request.size() != fields ) {
            throw std::runtime_error( "unsupported request envelope" );
        }
        if( kind == "observe" || kind == "pause" ) {
            if( kind == "pause" ) {
                paused = true;
                pause_origin = "host";
                pause_file();
                ++revision;
            }
            publish( id, "ready" );
            fs::remove( path( "claimed.json" ) );
            return false;
        }
        // Read-only observation must remain available to reconcile an expired
        // control claim after a crash. Recovery still excludes ordinary inputs.
        if( !waiting_interrupt.empty() || fs::exists( path( "control.json" ) ) ||
            fs::exists( path( "control-claimed.json" ) ) ) {
            throw std::runtime_error( "recovery is pending" );
        }
        ordinary_gate( request );
        if( kind == "resume" ) {
            if( !ordinary_receiver() ) {
                throw input_refusal( "unsupported boundary for resume" );
            }
            ordinary_commit_gate( request, true, false );
            fs::remove( path( "pause" ) );
            paused = false;
            pause_origin = "none";
            ++control_generation;
            ++revision;
            publish( id, "ready" );
            fs::remove( path( "claimed.json" ) );
            return false;
        }
        if( paused || fs::exists( path( "pause" ) ) ) {
            throw std::runtime_error( "paused; explicit resume required" );
        }
        if( !ordinary_receiver() ) {
            throw input_refusal( "boundary does not permit ordinary input" );
        }
        if( kind == "direct" && request.get_bool( "require_exact_frame" ) ) {
            throw input_refusal( "direct input requires physical-event preflight" );
        }
        std::optional<direct_input> direct;
        if( kind == "direct" ) {
            direct = direct_event( request.get_object( "input" ), mode );
            event = direct->engine;
        } else if( kind == "key" ) {
            event = key_event( request.get_string( "key" ), mode );
        } else if( kind == "action" ) {
            const std::string action = request.get_string( "action" );
            if( std::find( actions.begin(), actions.end(), action ) == actions.end() ) {
                throw input_refusal( "action not registered in active context" );
            }
            const auto &bindings = inp_mngr.get_input_for_action( action, category );
            const auto type = mode == keyboard_mode::keychar ? input_event_t::keyboard_char : input_event_t::keyboard_code;
            const auto binding = std::find_if( bindings.begin(), bindings.end(), [type]( const input_event & candidate ) {
                return candidate.type == type && candidate.sequence.size() == 1;
            } );
            if( binding == bindings.end() ) {
                throw input_refusal( "action has no single-key binding in current mode" );
            }
            event = *binding;
        } else {
            throw std::runtime_error( "unsupported command" );
        }
        ordinary_commit_gate( request, false, direct && direct->type == direct_input::kind::click );
        ++revision;
        pending = id;
        input_committed = true;
        publish( id, "dispatched", "", false );
        fs::remove( path( "claimed.json" ) );
        if( direct ) {
            feed_direct_imgui( *direct );
        }
        else { feed_imgui( event ); }
        return true;
    } catch( const std::exception &e ) {
        event = input_event();
        pending.clear();
        bool expected_refusal = dynamic_cast<const input_refusal *>( &e ) != nullptr;
        if( expected_refusal ) {
            try {
                std::ifstream claimed( path( "claimed.json" ) );
                // Upstream's JSON reader peeks beyond the closing brace and
                // clears ordinary EOF while seeking members. EOF is not I/O loss.
                claimed.exceptions( std::ios::badbit );
                if( !claimed.is_open() ) { throw std::runtime_error( "cannot read refusal claim" ); }
                TextJsonIn parser( claimed );
                const TextJsonObject original = parser.get_object();
                // This secondary read checks custody only; primary request validation stays strict.
                original.allow_omitted_members();
                authority_gate( original );
                if( integer_member( original, "takeover_generation" ) != takeover_generation ||
                    ( original.get_string( "kind" ) != "resume" &&
                      ( paused || fs::exists( path( "pause" ) ) ) ) || !saved_frame_ok ) {
                    expected_refusal = false;
                }
            } catch( const std::exception & ) { expected_refusal = false; }
        }
        std::error_code ignored;
        fs::remove( path( "claimed.json" ), ignored );
        if( ignored ) { expected_refusal = false; }
        // Widget delivery can already have effects before its bounded frame
        // completion fails. Preserve the nonterminal dispatched receipt so the
        // host records unknown delivery; never publish a zero-input rejection
        // or a later ready ACK for this original request.
        if( input_committed ) {
            try {
                fault_pause();
                publish( id, "dispatched", e.what(), false );
            } catch( const std::exception &fault ) {
                std::fprintf( stderr, "CDDA direct delivery fault: %s\n", fault.what() );
            }
            return false;
        }
        try {
            if( !expected_refusal ) { fault_pause(); }
            publish( id, "rejected", e.what() );
        } catch( const std::exception &publication_error ) {
            fault_pause();
            // This request never committed input. Preserve that known rejection
            // even when its fresh PNG failed; frame_ok=false cannot authorize input.
            try { publish( id, "rejected", publication_error.what(), false ); }
            catch( const std::exception &receipt_error ) {
                std::fprintf( stderr, "CDDA harness rejection publication failed: %s\n", receipt_error.what() );
            }
        }
        return false;
    }
}
} // namespace cdda_harness
