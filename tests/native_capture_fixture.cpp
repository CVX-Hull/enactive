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
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

class input_refusal : public std::runtime_error { using std::runtime_error::runtime_error; };
namespace fs = std::filesystem;
long long clock_ms = 1000;
long long now_ms() { return clock_ms; }
std::string path( const std::string &value ) { return value; }
struct frame_geometry { int width = 1; };
std::string session = "test", boundary_id = "test-b1", frame_boundary, frame_session;
std::string presented_boundary, presented_session, frame_name, frame_metadata;
std::string metadata = "all immutable metadata", pixels = "synthetic encoder bytes";
int revision = 1, frame_revision = -1, presented_revision = -1, frame_counter = 0;
long long takeover_generation = 0, presented_ms = 0, frame_ms = 0, last_publish = 0;
bool saved_frame_ok = false, dirty = true, encode_ok = true, authority_ok = true;
int geometry_width = 1, authority_checks = 0;
std::optional<frame_geometry> saved_geometry;
std::deque<std::string> retained_frames;
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
std::optional<frame_geometry> cached_frame_geometry() { return frame_geometry{ geometry_width }; }
std::string capture_metadata( const std::optional<frame_geometry> &geometry )
{
    return metadata + ":" + std::to_string( geometry->width );
}
struct JsonOut { explicit JsonOut( std::ostream &stream ) : stream( stream ) {} std::ostream &stream; };
void write_observation( JsonOut &out, const std::string &id, const std::string &status,
                        const std::string &, bool ok, const std::string &frame,
                        long long stamp, const std::optional<frame_geometry> & )
{
    // Line protocol for this fixture only; no substitute production JSON parser.
    out.stream << id << '\n' << status << '\n' << ok << '\n' << frame << '\n' << stamp << '\n';
}
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
    try { ordinary_gate( request ); } catch( const std::runtime_error & ) { return true; }
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
            require( bytes( "state.json" ).find( "\n1000\n" ) != std::string::npos );
        } else if( scenario == "explicit" ) {
            require( publish( "observe-2", "ready" ) );
            require( frame_name != first && frame_ms == 2000 && retained_frames.size() == 2 );
            require( rejected( request ) );
        } else if( scenario == "expiry" || scenario == "encoding-expiry" || scenario == "backwards" ) {
            if( scenario == "expiry" ) { clock_ms = 4000; }
            if( scenario == "backwards" ) { clock_ms = 999; }
            if( scenario == "encoding-expiry" ) { during_encode = []() { clock_ms = 4000; }; }
            require( publish( "", "ready" ) && frame_name != first && rejected( request ) );
        } else if( scenario == "changed-pixels" || scenario == "changed-geometry" || scenario == "changed-metadata" ) {
            if( scenario == "changed-pixels" ) { pixels += "changed"; }
            if( scenario == "changed-geometry" ) { ++geometry_width; }
            if( scenario == "changed-metadata" ) { metadata += "changed"; }
            require( publish( "", "ready" ) && frame_name != first && rejected( request ) );
            const std::string second = frame_name;
            pixels = "synthetic encoder bytes"; geometry_width = 1; metadata = "all immutable metadata";
            ++clock_ms;
            require( publish( "", "ready" ) && frame_name != first && frame_name != second );
        } else if( scenario == "failed-capture" ) {
            encode_ok = false;
            bool hard = false;
            try { publish( "", "ready" ); }
            catch( const input_refusal & ) { throw; }
            catch( const std::runtime_error & ) { hard = true; }
            require( hard && !saved_frame_ok && rejected( request ) );
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
            require( rejected( altered ) );
        } else { throw std::runtime_error( "unknown scenario" ); }
        std::cout << scenario << " passed\n";
    } catch( const std::exception &error ) { std::cerr << error.what() << '\n'; return 1; }
}
