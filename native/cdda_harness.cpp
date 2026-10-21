#include "cdda_harness.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <filesystem>
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
};
std::vector<input_scope> scopes;
std::string active_menu_query;
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
std::deque<std::string> retained_frames;

std::string path( const std::string &name )
{
    return directory + "/" + name;
}
void pause_file()
{
    std::ofstream out( path( "pause" ) );
    out << "paused\n";
    out.close();
    own_pause_time = fs::last_write_time( path( "pause" ) );
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
    out.member( "protocol", 5 );
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
                   presented_revision == revision && write_frame( path( "frame.tmp.png" ) );
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
                retained_frames.push_back( frame_name );
                if( retained_frames.size() > 120 ) {
                    std::error_code ignored;
                    fs::remove( path( retained_frames.front() ), ignored );
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
    stream << "{\"protocol\":5,\"id\":";
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
void ordinary_gate( const TextJsonObject &request )
{
    if( request.get_string( "session" ) != session || integer_member( request, "revision" ) != revision ||
        request.get_string( "boundary_id" ) != boundary_id ||
        integer_member( request, "takeover_generation" ) != takeover_generation ) {
        throw std::runtime_error( "stale session, revision, boundary or human generation; observe again" );
    }
    if( request.get_string( "frame" ) != frame_name || frame_name.empty() || !saved_frame_ok ||
        frame_boundary != boundary_id || frame_session != session || frame_revision != revision ||
        now_ms() - frame_ms > 3000 ||
        presented_boundary != boundary_id || presented_session != session ||
        presented_revision != revision || now_ms() - presented_ms > 3000 ||
        integer_member( request, "deadline_ms" ) < now_ms() ) {
        throw std::runtime_error( "fresh matching rendered boundary and deadline required" );
    }
    authority_gate( request );
}
bool same_frame_png( const std::string &saved, const std::string &latest, const struct stat &owned )
{
    constexpr off_t maximum_frame_bytes = 32 * 1024 * 1024;
    // Nonblocking opens cannot hang on a substituted FIFO; fstat rejects every
    // nonregular file and O_NOFOLLOW rejects symlinks before reading anything.
    const int saved_fd = open( saved.c_str(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK );
    const int latest_fd = open( latest.c_str(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK );
    struct stat saved_info = {};
    struct stat latest_info = {};
    bool same = saved_fd >= 0 && latest_fd >= 0 &&
                fstat( saved_fd, &saved_info ) == 0 && fstat( latest_fd, &latest_info ) == 0 &&
                S_ISREG( saved_info.st_mode ) && S_ISREG( latest_info.st_mode ) &&
                saved_info.st_size > 0 && saved_info.st_size <= maximum_frame_bytes &&
                saved_info.st_size == latest_info.st_size &&
                latest_info.st_dev == owned.st_dev && latest_info.st_ino == owned.st_ino;
    std::array<char, 32 * 1024> saved_chunk;
    std::array<char, 32 * 1024> latest_chunk;
    off_t remaining = saved_info.st_size;
    while( same && remaining > 0 ) {
        const off_t amount = std::min( remaining, static_cast<off_t>( saved_chunk.size() ) );
        const ssize_t saved_read = read( saved_fd, saved_chunk.data(), static_cast<size_t>( amount ) );
        const ssize_t latest_read = read( latest_fd, latest_chunk.data(), static_cast<size_t>( amount ) );
        // A short read or error (including EINTR) rejects without retrying work
        // beyond the request's original deadline.
        same = saved_read == amount && latest_read == amount &&
               std::equal( saved_chunk.begin(), saved_chunk.begin() + amount, latest_chunk.begin() );
        remaining -= amount;
    }
    char trailing;
    same = same && read( saved_fd, &trailing, 1 ) == 0 && read( latest_fd, &trailing, 1 ) == 0;
    if( saved_fd >= 0 && close( saved_fd ) != 0 ) { same = false; }
    if( latest_fd >= 0 && close( latest_fd ) != 0 ) { same = false; }
    return same;
}
void exact_frame_gate()
{
    // ordinary_gate has already matched the generated basename. Never capture
    // here: refresh_display has restored a different renderer target. The
    // existing encoder writes only the cached last-presented surface.
    const std::string saved = path( frame_name );
    const std::string latest = path( "frame.compare.tmp.png" );
    const int descriptor = open( latest.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600 );
    if( descriptor < 0 ) {
        throw std::runtime_error( "cannot exclusively create exact frame temporary file" );
    }
    struct stat owned = {};
    const bool identified = fstat( descriptor, &owned ) == 0;
    struct stat current = {};
    // One trusted bridge writer owns this pathname for the operation. The
    // existing encoder reopens it by name; concurrent external filesystem
    // mutation is outside this contract, not defeated by an inode check.
    const bool same = identified && lstat( latest.c_str(), &current ) == 0 &&
                      current.st_dev == owned.st_dev && current.st_ino == owned.st_ino &&
                      write_frame( latest ) && same_frame_png( saved, latest, owned );
    const bool closed = close( descriptor ) == 0;
    // Reject observed replacement. This pathname check/unlink is not atomic
    // protection against concurrent mutation by another same-user process.
    const bool removed = identified && lstat( latest.c_str(), &current ) == 0 &&
                         current.st_dev == owned.st_dev && current.st_ino == owned.st_ino &&
                         unlink( latest.c_str() ) == 0;
    if( !removed ) {
        throw std::runtime_error( "exact frame temporary file cleanup failed" );
    }
    if( !same || !closed ) {
        throw std::runtime_error( "latest presented PNG does not exactly match the saved frame or file I/O failed" );
    }
}
void ordinary_commit_gate( const TextJsonObject &request, bool resuming )
{
    ordinary_gate( request );
    if( !resuming && ( paused || fs::exists( path( "pause" ) ) ) ) {
        throw std::runtime_error( "pause interrupted dispatch" );
    }
    if( request.get_string( "kind" ) == "direct" &&
        ( !saved_geometry || current_frame_geometry() != saved_geometry ||
          cached_frame_geometry() != saved_geometry ) ) {
        throw std::runtime_error( "direct input requires unchanged attested frame geometry" );
    }
    if( request.get_bool( "require_exact_frame" ) ) {
        exact_frame_gate();
    }
    // The encoder/comparison can be slow. No game-thread input processing or
    // redraw interleaves it; queued physical input is handled by CheckMessages.
    // Host Pause still revokes the durable authority token, including Resume,
    // whose existing sentinel is intentionally consumed only after this gate.
    ordinary_gate( request );
    if( !waiting_interrupt.empty() || fs::exists( path( "control.json" ) ) ||
        fs::exists( path( "control-claimed.json" ) ) ) {
        throw std::runtime_error( "recovery is pending" );
    }
    if( integer_member( request, "deadline_ms" ) < now_ms() ) {
        throw std::runtime_error( "request expired before input commit" );
    }
    if( !resuming && ( paused || fs::exists( path( "pause" ) ) ) ) {
        throw std::runtime_error( "pause interrupted dispatch" );
    }
    // A window size/scale change during PNG comparison must also refuse before
    // committing the already-translated input, even without a processed event.
    if( request.get_string( "kind" ) == "direct" && current_frame_geometry() != saved_geometry ) {
        throw std::runtime_error( "frame geometry changed before input commit" );
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
// The host additionally checks Unicode printability categories. Native checks
// canonical UTF-8 and scalar/control structure without locale or Unicode tables.
int single_printable_scalar( const std::string &text )
{
    if( text.empty() || text.size() > 4 ) {
        throw std::runtime_error( "text must be one printable Unicode scalar" );
    }
    const uint32_t code = UTF8_getch( text );
    if( code > 0x10ffff || ( code >= 0xd800 && code <= 0xdfff ) ||
        code < 32 || ( code >= 127 && code <= 159 ) || code == 0x2028 || code == 0x2029 ||
        utf32_to_utf8( code ) != text ) {
        throw std::runtime_error( "text must be one canonical noncontrol Unicode scalar" );
    }
    // The pinned widget build uses ImWchar16. Refuse before dispatch instead
    // of allowing its UTF-8 decoder to silently substitute U+FFFD.
    if( code > IM_UNICODE_CODEPOINT_MAX ) {
        throw std::runtime_error( "Unicode scalar exceeds the pinned widget range" );
    }
    return static_cast<int>( code );
}
std::optional<frame_geometry> input_geometry( const TextJsonObject &input )
{
    const TextJsonObject geometry = input.get_object( "geometry" );
    if( geometry.size() != 5 || !geometry.has_array( "viewport" ) ) {
        throw std::runtime_error( "unsupported frame geometry" );
    }
    frame_geometry result;
    const auto dimension = [&]( const std::string &name ) {
        const long long value = integer_member( geometry, name );
        if( value <= 0 || value > 16384 ) { throw std::runtime_error( "invalid geometry dimension" ); }
        return static_cast<int>( value );
    };
    result.window_width = dimension( "window_width" );
    result.window_height = dimension( "window_height" );
    result.output_width = dimension( "output_width" );
    result.output_height = dimension( "output_height" );
    if( static_cast<long long>( result.output_width ) * result.output_height > 16777216 ) {
        throw std::runtime_error( "frame pixel limit exceeded" );
    }
    TextJsonArray viewport = geometry.get_array( "viewport" );
    if( viewport.size() != 4 ) { throw std::runtime_error( "invalid viewport" ); }
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
            if( ch < '0' || ch > '9' ) { throw std::runtime_error( "viewport requires nonnegative integer literals" ); }
        }
        raw->seek( end );
        if( number < 0 || number > 16384 ) { throw std::runtime_error( "invalid viewport coordinate" ); }
        result.viewport[index] = static_cast<int>( number );
    }
    if( !raw->end_array() ) { throw std::runtime_error( "invalid viewport length" ); }
    if( result.viewport[2] <= 0 || result.viewport[3] <= 0 ||
        result.viewport[0] + result.viewport[2] > result.output_width ||
        result.viewport[1] + result.viewport[3] > result.output_height ) {
        throw std::runtime_error( "viewport outside output" );
    }
    return result;
}
direct_input direct_event( const TextJsonObject &input, keyboard_mode mode )
{
    direct_input event;
    const std::string type = input.get_string( "type" );
    if( type == "key" ) {
        if( input.size() != 3 || !input.has_array( "modifiers" ) ) {
            throw std::runtime_error( "unsupported direct key shape" );
        }
        const std::string key = input.get_string( "key" );
        // key_event is pure; unlike SDL's keychar translator it never reads
        // held physical keys or touches arrow-combination state.
        event.engine = key_event( key, keyboard_mode::keycode );
        TextJsonArray modifiers = input.get_array( "modifiers" );
        if( modifiers.size() > 3 ) { throw std::runtime_error( "too many key modifiers" ); }
        std::set<keymod_t> explicit_modifiers;
        for( const std::string modifier : modifiers ) {
            keymod_t parsed;
            if( modifier == "CTRL" ) { parsed = keymod_t::ctrl; }
            else if( modifier == "ALT" ) { parsed = keymod_t::alt; }
            else if( modifier == "SHIFT" ) { parsed = keymod_t::shift; }
            else { throw std::runtime_error( "unsupported key modifier" ); }
            if( !explicit_modifiers.insert( parsed ).second ) {
                throw std::runtime_error( "duplicate key modifier" );
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
                throw std::runtime_error( "unsupported keychar modifier combination" );
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
        if( input.size() != 2 ) { throw std::runtime_error( "unsupported direct text shape" ); }
        const std::string text = input.get_string( "text" );
        const int code = single_printable_scalar( text );
        event.type = direct_input::kind::text;
        event.engine = input_event( code, input_event_t::keyboard_char );
        event.engine.text = text;
        event.widget_text = text;
    } else if( type == "click" ) {
        if( input.size() != 5 ) { throw std::runtime_error( "unsupported direct click shape" ); }
        const std::string button = input.get_string( "button" );
        if( button != "left" && button != "right" ) { throw std::runtime_error( "unsupported click button" ); }
        const auto geometry = input_geometry( input );
        const long long x = integer_member( input, "x" );
        const long long y = integer_member( input, "y" );
        if( !geometry || geometry != saved_geometry || x < 0 || y < 0 ||
            x >= geometry->output_width || y >= geometry->output_height ) {
            throw std::runtime_error( "click requires matching geometry and an in-frame pixel" );
        }
        event.type = direct_input::kind::click;
        event.right_button = button == "right";
        event.engine = input_event( event.right_button ? MouseInput::RightButtonReleased : MouseInput::LeftButtonReleased,
                                    input_event_t::mouse );
        event.engine.mouse_pos = point( static_cast<int>( x * geometry->window_width / geometry->output_width ),
                                       static_cast<int>( y * geometry->window_height / geometry->output_height ) );
        event.widget_position = point( static_cast<int>( x ), static_cast<int>( y ) );
    } else {
        throw std::runtime_error( "unsupported direct input type" );
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
        if( request.size() != fields || integer_member( request, "protocol" ) != 5 ||
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
        pause_origin = "fault";
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
        "INVENTORY", "INVENTORY_SELECTOR", "LIST_ITEMS", "LIST_MONSTERS",
        "CRAFTING", "CONSTRUCTION", "SCROLLABLE_TEXT", "HELP_KEYBINDINGS",
        "HELP", "LOOK", "LOOK_CLOSE", "OVERMAP", "CONFIRMATION",
        "DISPLAY_HELP", "MESSAGE_LOG", "PLAYER_INFO", "PICK_WORLD_DIALOG",
        "MODMANAGER_DIALOG", "WORLDGEN_CONFIRM_DIALOG", "MELEE_STYLE_PICKER",
        "NEW_CHAR_POINTS", "NEW_CHAR_STATS", "NEW_CHAR_TRAITS", "NEW_CHAR_PROFESSIONS",
        "NEW_CHAR_SKILLS", "NEW_CHAR_SCENARIOS", "NEW_CHAR_DESCRIPTION"
    };
    boundary_kind kind = menus.count( name ) ? boundary_kind::menu : boundary_kind::unsupported;
    // Only an exact pinned owner wait may admit a generic category. Keep native
    // bindings and exclude enclosing scopes and nested input contexts.
    if( !active_menu_query.empty() && name == active_menu_query && scopes.empty() && in_game ) {
        kind = boundary_kind::menu;
    }
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
menu_query::menu_query( const std::string &category ) :
    active( in_game && scopes.empty() && active_menu_query.empty() && !category.empty() )
{
    if( active ) {
        active_menu_query = category;
    }
}
menu_query::~menu_query()
{
    if( active ) {
        active_menu_query.clear();
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
        pause_origin = "fault";
        pause_file();
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
    bool direct_committed = false;
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
            paused = true;
            pause_origin = "fault";
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
        if( integer_member( request, "protocol" ) != 5 ) {
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
            if( current_kind != boundary_kind::normal_play && current_kind != boundary_kind::menu ) {
                throw std::runtime_error( "unsupported boundary for resume" );
            }
            ordinary_commit_gate( request, true );
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
        if( current_kind != boundary_kind::normal_play && current_kind != boundary_kind::menu ) {
            throw std::runtime_error( "boundary does not permit ordinary input" );
        }
        if( kind == "direct" && !request.get_bool( "require_exact_frame" ) ) {
            throw std::runtime_error( "direct input requires exact frame preflight" );
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
        ordinary_commit_gate( request, false );
        ++revision;
        pending = id;
        publish( id, "dispatched", "", false );
        fs::remove( path( "claimed.json" ) );
        if( direct ) {
            direct_committed = true;
            feed_direct_imgui( *direct );
        }
        else { feed_imgui( event ); }
        return true;
    } catch( const std::exception &e ) {
        event = input_event();
        pending.clear();
        std::error_code ignored;
        fs::remove( path( "claimed.json" ), ignored );
        // Widget delivery can already have effects before its bounded frame
        // completion fails. Preserve the nonterminal dispatched receipt so the
        // host records unknown delivery; never publish a zero-input rejection
        // or a later ready ACK for this original request.
        if( direct_committed ) {
            paused = true;
            pause_origin = "fault";
            try {
                pause_file();
                publish( id, "dispatched", e.what(), false );
            } catch( const std::exception &fault ) {
                std::fprintf( stderr, "CDDA direct delivery fault: %s\n", fault.what() );
            }
            return false;
        }
        try {
            publish( id, "rejected", e.what() );
        } catch( const std::exception &publication_error ) {
            paused = true;
            pause_origin = "fault";
            pause_file();
            std::fprintf( stderr, "CDDA harness publication failed: %s\n", publication_error.what() );
        }
        return false;
    }
}
} // namespace cdda_harness
