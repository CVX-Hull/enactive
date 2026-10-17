#include "cdda_harness.h"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <fcntl.h>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <cctype>
#include <stdexcept>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

#include "avatar.h"
#include "calendar.h"
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
int last_turn = -1;
bool dirty = true;
struct input_scope {
    boundary_kind kind;
    std::string category;
    std::vector<std::string> actions;
    bool input;
};
std::vector<input_scope> scopes;
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
    if( current_kind != effective || category != top.category || actions != top.actions ||
        boundary_id.empty() ) {
        current_kind = effective;
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
int frame_revision = -1;
long long frame_ms = 0;
bool saved_frame_ok = false;
std::deque<std::string> retained_frames;

std::string path( const std::string &name )
{
    return directory + "/" + name;
}
void pause_file()
{
    std::ofstream out( path( "pause" ) );
    out << "paused\n";
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
                        const std::string &error, bool frame_ok, const std::string &published_frame )
{
    out.start_object();
    out.member( "protocol", 3 );
    out.member( "id", id );
    out.member( "session", session );
    out.member( "revision", revision );
    out.member( "category", category );
    out.member( "actions", actions );
    out.member( "status", status );
    out.member( "error", error );
    out.member( "paused", paused );
    out.member( "timestamp_ms", frame_ok ? presented_ms : now_ms() );
    out.member( "frame_ok", frame_ok );
    out.member( "frame", published_frame );
    out.member( "boundary" );
    out.start_object();
    out.member( "kind", kind_name( current_kind ) );
    out.member( "id", boundary_id );
    out.member( "control_generation", control_generation );
    std::vector<std::string> operations;
    if( current_kind == boundary_kind::activity_poll && activity_eligible ) {
        operations.push_back( "request_interrupt" );
    } else if( current_kind == boundary_kind::interrupt_confirmation && !owned_interrupt.empty() ) {
        operations.push_back( "answer_interrupt" );
    } else if( current_kind == boundary_kind::debug_prompt ) {
        operations.push_back( "continue_debug_once" );
    }
    out.member( "recovery_operations", operations );
    out.member( "interrupt_request_id" );
    if( current_kind == boundary_kind::interrupt_confirmation && !owned_interrupt.empty() ) {
        out.write( owned_interrupt );
    } else {
        out.write_null();
    }
    out.end_object();
    out.member( "in_game", in_game );
    scene( out );
    out.end_object();
}
bool publish( const std::string &id, const std::string &status,
              const std::string &error = "", bool capture = true )
{
    bool frame_ok = false;
    std::string published_frame;
    if( capture ) {
        saved_frame_ok = false;
        // Present and copy this boundary's current render buffer. A cached front
        // buffer from an earlier prompt must never acquire a new timestamp.
        ui_manager::redraw();
        refresh_display();
        frame_ok = presented_boundary == boundary_id && presented_session == session &&
                   presented_revision == revision && write_frame( path( "frame.tmp.png" ) );
        if( frame_ok ) {
            frame_name = "frame-" + session + "-" + std::to_string( ++frame_counter ) + ".png";
            fs::rename( path( "frame.tmp.png" ), path( frame_name ) );
            fs::copy_file( path( frame_name ), path( "frame.latest.png" ), fs::copy_options::overwrite_existing );
            fs::rename( path( "frame.latest.png" ), path( "frame.png" ) );
            published_frame = frame_name;
            frame_boundary = boundary_id;
            frame_session = session;
            frame_revision = revision;
            frame_ms = presented_ms;
            saved_frame_ok = true;
            retained_frames.push_back( frame_name );
            if( retained_frames.size() > 120 ) {
                std::error_code ignored;
                fs::remove( path( retained_frames.front() ), ignored );
                retained_frames.pop_front();
            }
        }
    }
    const std::string output = id.empty() ? "state.json" : "response.json";
    std::ofstream stream( path( output + ".tmp" ) );
    stream.exceptions( std::ios::badbit | std::ios::failbit );
    JsonOut out( stream );
    write_observation( out, id, status, error, frame_ok, published_frame );
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
    stream << "{\"protocol\":3,\"id\":";
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
        throw std::runtime_error( "key must be one ASCII character or supported named key" );
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
input_event action_event( const std::string &action, keyboard_mode mode, bool confirmation = false )
{
    if( std::find( actions.begin(), actions.end(), action ) == actions.end() ) {
        throw std::runtime_error( "recovery action not registered" );
    }
    const auto &bindings = inp_mngr.get_input_for_action( action, category );
    const auto type = mode == keyboard_mode::keychar ? input_event_t::keyboard_char : input_event_t::keyboard_code;
    const auto binding = std::find_if( bindings.begin(), bindings.end(), [type, confirmation]( const input_event & candidate ) {
        return candidate.type == type && candidate.sequence.size() == 1 &&
               ( !confirmation || !get_option<bool>( "FORCE_CAPITAL_YN" ) ||
                 input_context::disallow_lower_case_or_non_modified_letters( candidate ) );
    } );
    if( binding == bindings.end() ) {
        throw std::runtime_error( "recovery action has no usable single-key binding" );
    }
    return *binding;
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
        if( request.size() != fields || integer_member( request, "protocol" ) != 3 ||
            created < 0 || created > now_ms() + 1000 || deadline != created + 2000 || deadline < now_ms() ) {
            throw std::runtime_error( "unsupported control envelope or expired request" );
        }
        if( request.get_string( "session" ) != session ||
            integer_member( request, "control_generation" ) != control_generation ) {
            throw std::runtime_error( "stale control session or generation" );
        }
        authority_gate( request );
        if( kind == "request_interrupt" ) {
            if( current_kind != boundary_kind::activity_poll || !activity_eligible ) {
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
                if( current_kind != boundary_kind::interrupt_confirmation || owned_interrupt.empty() ||
                    request.get_string( "interrupt_request_id" ) != owned_interrupt ||
                    ( choice != "YES" && choice != "NO" ) ) {
                    throw std::runtime_error( "control does not own this confirmation" );
                }
                event = action_event( choice, mode, true );
            } else {
                if( current_kind != boundary_kind::debug_prompt ) {
                    throw std::runtime_error( "debug continuation requires raw debug boundary" );
                }
                event = key_event( "SPACE", mode );
            }
        }
        paused = true;
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
        ++control_generation;
        ++revision;
        dirty = true;
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
        paused = true;
        pause_file();
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

bool enabled()
{
    return !directory.empty();
}

scope::scope( boundary_kind kind )
{
    scopes.push_back( { kind, kind == boundary_kind::debug_prompt ? "DEBUG_MSG" : "", {}, false } );
    if( kind == boundary_kind::debug_prompt ) {
        sync_scope();
        // Consecutive errors can have the same category with no rendered caller
        // between them. Every raw prompt invocation still owns a new identity.
        new_boundary();
    }
}
scope::scope( const std::string &name, const std::vector<std::string> &registered )
{
    // Coverage is deliberately explicit. In particular DEFAULTMODE in keybinding
    // settings, deathcam and unknown callers is never promoted by its name.
    static const std::set<std::string> menus = {
        "MAIN_MENU", "UILIST", "YESNO", "POPUP_WAIT", "STRING_INPUT",
        "INVENTORY", "INVENTORY_SELECTOR", "SCROLLABLE_TEXT", "HELP_KEYBINDINGS",
        "HELP", "LOOK", "LOOK_CLOSE", "OVERMAP", "CONFIRMATION",
        "DISPLAY_HELP", "MESSAGE_LOG", "PLAYER_INFO", "PICK_WORLD_DIALOG",
        "MODMANAGER_DIALOG", "WORLDGEN_CONFIRM_DIALOG", "MELEE_STYLE_PICKER",
        "NEW_CHAR_POINTS", "NEW_CHAR_STATS", "NEW_CHAR_TRAITS", "NEW_CHAR_PROFESSIONS",
        "NEW_CHAR_SKILLS", "NEW_CHAR_SCENARIOS", "NEW_CHAR_DESCRIPTION"
    };
    boundary_kind kind = menus.count( name ) ? boundary_kind::menu : boundary_kind::unsupported;
    const bool nested = std::any_of( scopes.begin(), scopes.end(),
    []( const input_scope & entry ) { return entry.input; } );
    if( query_depth > 0 && !owned_interrupt.empty() && name == "YESNO" &&
        static_cast<int>( scopes.size() ) == query_input_depth ) {
        kind = boundary_kind::interrupt_confirmation;
    } else if( !scopes.empty() && scopes.back().kind == boundary_kind::debug_prompt ) {
        kind = boundary_kind::debug_prompt;
    } else if( !nested && !scopes.empty() && name == "DEFAULTMODE" ) {
        if( scopes.back().kind == boundary_kind::activity_poll ) {
            kind = boundary_kind::activity_poll;
        } else if( scopes.back().kind == boundary_kind::normal_play && in_game ) {
            kind = boundary_kind::normal_play;
        }
    }
    scopes.push_back( { kind, name, registered, true } );
    sync_scope();
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
    ++control_generation;
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
        return;
    }
    sync_scope();
    const int turn = in_game ? to_turn<int>( calendar::turn ) : -1;
    if( turn != last_turn ) {
        last_turn = turn;
        ++revision;
        dirty = true;
    }
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
        if( !waiting_interrupt.empty() && current_kind == boundary_kind::interrupt_confirmation &&
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
        paused = true;
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
    try {
        if( fs::exists( path( "pause" ) ) && !paused ) {
            paused = true;
            ++revision;
            dirty = true;
        }
        try {
            if( poll_control( mode, event ) ) {
                return true;
            }
        } catch( const std::exception &error ) {
            paused = true;
            pause_file();
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
        if( request.get_int( "protocol" ) != 3 ) {
            throw std::runtime_error( "unsupported protocol" );
        }
        const std::string kind = request.get_string( "kind" );
        if( request.get_float( "deadline_ms" ) < now_ms() ) {
            throw std::runtime_error( "expired request" );
        }
        if( kind == "observe" || kind == "pause" ) {
            if( kind == "pause" ) {
                paused = true;
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
        if( request.get_string( "session" ) != session || request.get_int( "revision" ) != revision ) {
            throw std::runtime_error( "stale session or revision; observe again" );
        }
        if( kind == "resume" ) {
            if( current_kind != boundary_kind::normal_play && current_kind != boundary_kind::menu ) {
                throw std::runtime_error( "unsupported boundary for resume" );
            }
            if( presented_boundary != boundary_id || presented_session != session ||
                presented_revision != revision || now_ms() - presented_ms > 3000 ) {
                throw std::runtime_error( "fresh matching rendered boundary required" );
            }
            authority_gate( request );
            fs::remove( path( "pause" ) );
            paused = false;
            ++control_generation;
            ++revision;
            publish( id, "ready" );
            fs::remove( path( "claimed.json" ) );
            return false;
        }
        if( paused || fs::exists( path( "pause" ) ) ) {
            throw std::runtime_error( "paused; explicit resume required" );
        }
        if( current_kind != boundary_kind::normal_play && current_kind != boundary_kind::menu ) {
            throw std::runtime_error( "boundary does not permit ordinary input" );
        }
        if( kind == "key" ) {
            event = key_event( request.get_string( "key" ), mode );
        } else if( kind == "action" ) {
            const std::string action = request.get_string( "action" );
            if( std::find( actions.begin(), actions.end(), action ) == actions.end() ) {
                throw std::runtime_error( "action not registered in active context" );
            }
            const auto &bindings = inp_mngr.get_input_for_action( action, category );
            const auto type = mode == keyboard_mode::keychar ? input_event_t::keyboard_char : input_event_t::keyboard_code;
            const auto binding = std::find_if( bindings.begin(), bindings.end(), [type]( const input_event & candidate ) {
                return candidate.type == type && candidate.sequence.size() == 1;
            } );
            if( binding == bindings.end() ) {
                throw std::runtime_error( "action has no single-key binding in current mode" );
            }
            event = *binding;
        } else {
            throw std::runtime_error( "unsupported command" );
        }
        if( fs::exists( path( "pause" ) ) ) {
            throw std::runtime_error( "pause interrupted dispatch" );
        }
        if( presented_boundary != boundary_id || presented_session != session ||
            presented_revision != revision || now_ms() - presented_ms > 3000 ) {
            throw std::runtime_error( "fresh matching rendered boundary required" );
        }
        authority_gate( request );
        ++revision;
        pending = id;
        publish( id, "dispatched", "", false );
        fs::remove( path( "claimed.json" ) );
        feed_imgui( event );
        return true;
    } catch( const std::exception &e ) {
        event = input_event();
        pending.clear();
        std::error_code ignored;
        fs::remove( path( "claimed.json" ), ignored );
        try {
            publish( id, "rejected", e.what() );
        } catch( const std::exception &publication_error ) {
            paused = true;
            pause_file();
            std::fprintf( stderr, "CDDA harness publication failed: %s\n", publication_error.what() );
        }
        return false;
    }
}
} // namespace cdda_harness
