// Component fixture for the production publish/gate/filesystem functions.
// Rendering, observation serialization and authority are explicit test doubles.
// This does not qualify SDL encoding, CDDA gameplay or a normal game ending.
#include <algorithm>
#include <array>
#include <deque>
#include <filesystem>
#include <fcntl.h>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

class input_refusal : public std::runtime_error { using std::runtime_error::runtime_error; };
namespace fs = std::filesystem;
long long clock_ms = 1000;
long long now_ms() { return clock_ms; }
std::string path( const std::string &value ) { return value; }
struct frame_geometry {
    int window_width = 1, window_height = 1, output_width = 1, output_height = 1;
    std::vector<int> viewport = {0, 0, 1, 1};
};
std::string session = "test", boundary_id = "test-b1", frame_boundary, frame_session;
std::string presented_boundary, presented_session, frame_name, frame_metadata;
std::string metadata = "all immutable metadata", pixels = "synthetic encoder bytes";
int revision = 1, frame_revision = -1, presented_revision = -1, frame_counter = 0;
long long takeover_generation = 0, presented_ms = 0, frame_ms = 0, last_publish = 0;
bool saved_frame_ok = false, dirty = true, encode_ok = true, authority_ok = true;
int geometry_width = 1, authority_checks = 0;
std::optional<frame_geometry> saved_geometry;
// PRODUCTION_RECORDS
std::function<void()> during_encode;
namespace ui_manager { void redraw() {} }
void refresh_display()
{
    presented_boundary = boundary_id;
    presented_session = session;
    presented_revision = revision;
    presented_ms = now_ms();
}
bool write_frame( const std::string &name )
{
    if( during_encode ) { during_encode(); }
    if( !encode_ok ) { return false; }
    std::ofstream( name ) << pixels;
    return true;
}
std::optional<frame_geometry> cached_frame_geometry()
{
    return frame_geometry{ geometry_width, 1, geometry_width, 1, {0, 0, geometry_width, 1} };
}
// Deterministic token writer double; production write_observation and
// capture_metadata select and normalize every observation field themselves.
struct JsonOut {
    explicit JsonOut( std::ostream &stream ) : stream( stream ) {}
    std::ostream &stream;
    void start_object() { stream << '{'; }
    void end_object() { stream << '}'; }
    void start_array() { stream << '['; }
    void end_array() { stream << ']'; }
    void write_null() { stream << "null;"; }
    void write( const std::string &value ) { stream << value.size() << ':' << value << ';'; }
    void write( const char *value ) { write( std::string( value ) ); }
    template<typename T> void write( const T &value ) { stream << value << ';'; }
    template<typename T> void write( const std::vector<T> &value ) {
        start_array(); for( const auto &entry : value ) { write( entry ); } end_array();
    }
    void member( const std::string &key ) { write( key ); }
    template<typename T> void member( const std::string &key, const T &value ) { member( key ); write( value ); }
};
std::string category = "fixture menu", pause_origin = "none", presented_ui, ui_boundary, ui_session;
std::vector<std::string> actions = {"fixture action"};
int control_generation = 0, ui_revision = -1;
bool paused = false, in_game = true, activity_eligible = false;
std::string owned_interrupt;
std::optional<std::string> presented_ui_data;
enum class boundary_kind { activity_poll, interrupt_confirmation, debug_prompt };
boundary_kind current_kind = boundary_kind::activity_poll;
std::string kind_name( boundary_kind ) { return "fixture boundary"; }
bool ordinary_receiver() { return true; }
bool recovery_receiver( boundary_kind ) { return false; }
void write_ui( JsonOut &out, const std::string &ui ) { out.write( ui ); }
std::function<void()> during_metadata;
void scene( JsonOut &out ) {
    if( during_metadata ) { during_metadata(); }
    out.member( "scene", metadata );
}
// PRODUCTION_SERIALIZER
struct TextJsonObject {
    std::map<std::string, std::string> strings;
    std::map<std::string, long long> integers;
    std::string get_string( const std::string &key ) const { return strings.at( key ); }
};
long long integer_member( const TextJsonObject &request, const std::string &key )
{
    return request.integers.at( key );
}
void authority_gate( const TextJsonObject & )
{
    ++authority_checks;
    if( !authority_ok ) { throw std::runtime_error( "revoked" ); }
}
bool same_frame_png( const std::string &, const std::string &, const struct stat & );

// PRODUCTION_FUNCTIONS

void require( bool value ) { if( !value ) { throw std::runtime_error( "assertion failed" ); } }
std::string bytes( const std::string &file )
{
    std::ifstream stream( file );
    return { std::istreambuf_iterator<char>( stream ), std::istreambuf_iterator<char>() };
}
TextJsonObject request_for_current_frame()
{
    return { { { "session", session }, { "boundary_id", boundary_id }, { "frame", frame_name } },
        { { "revision", revision }, { "takeover_generation", takeover_generation }, { "deadline_ms", 20000 } } };
}
bool rejected( const TextJsonObject &request )
{
    try { ordinary_gate( request ); } catch( const input_refusal & ) { return true; }
    return false;
}
bool faulted( const TextJsonObject &request )
{
    try { ordinary_gate( request ); } catch( const input_refusal & ) { throw; }
    catch( const std::runtime_error & ) { return true; }
    return false;
}
int main( int argc, char **argv )
{
    try {
        require( argc == 2 && publish( "observe-1", "ready" ) );
        const std::string first = frame_name, original = bytes( first );
        const long long stamp = frame_ms;
        const auto request = request_for_current_frame();
        clock_ms = 2000;
        const std::string scenario = argv[1];
        if( scenario == "heartbeat" ) {
            // poll has already chosen its passive branch; host publishes while
            // encoding is in progress, then native claims/gates that same input.
            during_encode = [&]() { std::ofstream( "host-request" ) << request.get_string( "frame" ); };
            require( publish( "", "ready" ) );
            require( bytes( "host-request" ) == frame_name && !rejected( request ) );
            require( authority_checks == 1 && frame_name == first && frame_ms == stamp );
            require( retained_frames.size() == 1 && frame_counter == 1 && bytes( first ) == original );
            require( bytes( "state.json" ).find( "12:timestamp_ms;1000;" ) != std::string::npos );
        } else if( scenario == "explicit" ) {
            require( publish( "observe-2", "ready" ) );
            require( frame_name != first && frame_ms == 2000 && retained_frames.size() == 2 );
            require( !rejected( request ) && frame_ms != stamp );
        } else if( scenario == "expiry" || scenario == "encoding-expiry" || scenario == "backwards" ) {
            if( scenario == "expiry" ) { clock_ms = 4001; }
            if( scenario == "backwards" ) { clock_ms = 999; }
            if( scenario == "encoding-expiry" ) { during_encode = []() { clock_ms = 4001; }; }
            require( publish( "", "ready" ) && frame_name != first && rejected( request ) );
        } else if( scenario == "changed-pixels" || scenario == "changed-geometry" || scenario == "changed-metadata" ) {
            if( scenario == "changed-pixels" ) { pixels += "changed"; }
            if( scenario == "changed-geometry" ) { ++geometry_width; }
            if( scenario == "changed-metadata" ) { metadata += "changed"; }
            require( publish( "", "ready" ) && frame_name != first );
            require( rejected( request ) == ( scenario != "changed-pixels" ) );
            require( bytes( first ) == original );
            const std::string second = frame_name;
            pixels = "synthetic encoder bytes"; geometry_width = 1; metadata = "all immutable metadata";
            ++clock_ms;
            require( publish( "", "ready" ) && frame_name != first && frame_name != second );
        } else if( scenario == "ttl-boundary" ) {
            clock_ms = stamp + 3000;
            require( publish( "", "ready" ) && frame_name != first && !rejected( request ) );
        } else if( scenario == "original-ttl" ) {
            pixels += "changed";
            require( publish( "", "ready" ) && frame_name != first && !rejected( request ) );
            clock_ms = stamp + 3001;
            require( publish( "observe-fresh", "ready" ) && frame_ms == clock_ms );
            require( rejected( request ) && !rejected( request_for_current_frame() ) );
        } else if( scenario == "current-metadata" ) {
            metadata += "changed without revision";
            require( rejected( request ) );
        } else if( scenario == "metadata-expiry" ) {
            // Serialization itself consumes time. Equal metadata cannot conceal
            // expiry crossed while evaluating it; neither clock is renewed.
            during_metadata = []() { clock_ms = 4001; };
            require( rejected( request ) && frame_ms == stamp );
        } else if( scenario.find( "metadata-" ) == 0 ) {
            if( scenario == "metadata-category" ) { category += "changed"; }
            else if( scenario == "metadata-actions" ) { actions.push_back( "new action" ); }
            else if( scenario == "metadata-control" ) { ++control_generation; }
            else if( scenario == "metadata-ui" ) {
                presented_ui = "new ui"; presented_ui_data = presented_ui;
                ui_session = session; ui_boundary = boundary_id; ui_revision = revision;
            }
            else if( scenario == "metadata-pause-origin" ) { pause_origin = "operator"; }
            else if( scenario == "metadata-in-game" ) { in_game = false; }
            else { throw std::runtime_error( "unknown metadata field" ); }
            require( rejected( request ) );
        } else if( scenario == "unknown" || scenario == "foreign" ) {
            auto altered = request;
            altered.strings["frame"] = scenario == "unknown" ? "never-issued.png" : "frame-foreign-1.png";
            std::ofstream( altered.get_string( "frame" ) ) << original;
            require( rejected( altered ) );
        } else if( scenario == "evicted" ) {
            for( int i = 0; i < 120; ++i ) { require( publish( "observe-next", "ready" ) ); }
            require( retained_frames.size() == 120 && !fs::exists( first ) && rejected( request ) );
            std::ofstream( first ) << original;
            require( rejected( request ) );
        } else if( scenario == "failed-capture" ) {
            encode_ok = false;
            bool hard = false;
            try { publish( "", "ready" ); }
            catch( const input_refusal & ) { throw; }
            catch( const std::runtime_error & ) { hard = true; }
            require( hard && !saved_frame_ok && faulted( request ) );
            encode_ok = true;
            require( publish( "", "ready" ) && frame_name != first );
        } else if( scenario == "missing-file" ) {
            fs::remove( first );
            bool hard = false;
            try { publish( "", "ready" ); }
            catch( const input_refusal & ) { throw; }
            catch( const std::runtime_error & ) { hard = true; }
            require( hard );
        } else if( scenario == "authority" || scenario == "deadline" || scenario == "source-age" ) {
            require( publish( "", "ready" ) && frame_name == first );
            auto altered = request;
            if( scenario == "authority" ) { authority_ok = false; }
            if( scenario == "deadline" ) { altered.integers["deadline_ms"] = clock_ms - 1; }
            if( scenario == "source-age" ) { clock_ms = 4001; }
            require( scenario == "authority" ? faulted( altered ) : rejected( altered ) );
        } else { throw std::runtime_error( "unknown scenario" ); }
        std::cout << scenario << " passed\n";
    } catch( const std::exception &error ) { std::cerr << error.what() << '\n'; return 1; }
}
