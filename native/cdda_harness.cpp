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
#include <stdexcept>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

#include "avatar.h"
#include "calendar.h"
#include "game.h"
#include "input.h"
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
    if( current_kind != top.kind || category != top.category || actions != top.actions ||
        boundary_id.empty() ) {
        current_kind = top.kind;
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
void publish( const std::string &id, const std::string &status,
              const std::string &error = "", bool capture = true )
{
    bool frame_ok = false;
    std::string published_frame;
    if( capture ) {
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
    out.start_object();
    out.member( "protocol", 2 );
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
    out.member( "recovery_operations", std::vector<std::string>() );
    out.member( "interrupt_request_id" );
    out.write_null();
    out.end_object();
    out.member( "in_game", in_game );
    scene( out );
    out.end_object();
    stream.close();
    fs::rename( path( output + ".tmp" ), path( output ) );
    if( !id.empty() ) {
        fs::copy_file( path( output ), path( "state.json.tmp" ), fs::copy_options::overwrite_existing );
        fs::rename( path( "state.json.tmp" ), path( "state.json" ) );
    }
    dirty = false;
    last_publish = now_ms();
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
    const int counter = admitted.get_int( "counter" );
    if( admitted.size() != 2 || live.size() != 2 || boot.empty() || counter < 0 ||
        live.get_string( "controller_boot_id" ) != boot || live.get_int( "counter" ) != counter ) {
        throw std::runtime_error( "host authority revoked or malformed" );
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
    if( !scopes.empty() && scopes.back().kind == boundary_kind::debug_prompt ) {
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
    scopes.pop_back();
    // Restoration is lazy until rendering/input: repeated timeout polls in the
    // same context keep their identity, while a nested observed UI changes it.
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
    if( directory.empty() || !scoped() || !pending.empty() || now_ms() - last_poll < 25 ) {
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
        if( request.get_int( "protocol" ) != 2 ) {
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
