// Compiled production UI/renderer seam with explicit engine/JSON doubles.
// No SDL, game state, native usefulness or graphical qualification is claimed.
#include <algorithm>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

struct JsonOut {
    std::ostream &out;
    std::vector<bool> first;
    bool named = false;
    explicit JsonOut( std::ostream &s ) : out( s ) {}
    void prefix() {
        if( named ) { named = false; return; }
        if( !first.empty() ) { if( !first.back() ) { out << ','; } first.back() = false; }
    }
    void start_object() { prefix(); out << '{'; first.push_back( true ); }
    void end_object() { out << '}'; first.pop_back(); }
    void start_array() { prefix(); out << '['; first.push_back( true ); }
    void end_array() { out << ']'; first.pop_back(); }
    void write( const std::string &s ) { prefix(); out << std::quoted( s ); }
    void write( const char *s ) { write( std::string( s ) ); }
    void write( bool b ) { prefix(); out << ( b ? "true" : "false" ); }
    void write_null() { prefix(); out << "null"; }
    void member( const std::string &name ) { prefix(); out << std::quoted( name ) << ':'; named = true; }
    template<typename T> void member( const std::string &name, const T &value ) { member( name ); write( value ); }
};
namespace cdda_harness {
// PRODUCTION_UI_TYPES
bool ui_top = false, harness_enabled = true;
std::optional<visible_ui> staged_ui;
bool enabled() { return harness_enabled; }
// PRODUCTION_UI_SERIALIZER
// PRODUCTION_UI_FUNCTIONS
}
struct point { int x, y; point( int x, int y ) : x( x ), y( y ) {} };
struct window { int width = 40, height = 4; };
int getmaxx( const window &w ) { return w.width; }
int getmaxy( const window &w ) { return w.height; }
constexpr int c_dark_gray = 1, c_light_green = 2;
using nc_color = int;
bool selecting = true, activatable_value = true, multiselect = true, symbols = false;
bool allows_selecting() { return selecting; }
bool activatable() { return activatable_value; }
template<typename T> T get_option( const std::string & ) { return symbols; }
std::string remove_color_tags( const std::string &s ) { return s; }
std::string trim_by_length( const std::string &s, size_t n ) { return s.substr( 0, n ); }
struct item { int color() const { return 3; } char symbol() const { return '!'; } };
struct entry_type {
    bool item_value = true, enabled = true;
    size_t chosen_count = 0, available = 2;
    bool is_item() const { return item_value; }
    bool is_selectable() const { return enabled; }
    char get_invlet() const { return 'a'; }
    int get_invlet_color() const { return 3; }
    size_t get_available_count() const { return available; }
    const item *any_item() const { static item value; return &value; }
};
struct drawn_cell { int x, y; char glyph; };
std::vector<drawn_cell> draws;
void mvwputch( const window &, const point &p, int, char c ) { draws.push_back( {p.x, p.y, c} ); }
void draw_row( entry_type entry, point p, window win, int yy, bool selected = true, bool label_present = true )
{
    size_t cell_index = 0;
    int text_x = 0;
    size_t text_width = 4;
    std::string text = "item";
// PRODUCTION_ROW_LOCALS
    if( label_present ) {
// PRODUCTION_LABEL_HOOK
    }
// PRODUCTION_DRAW_TAIL
}
int main( int argc, char **argv )
{
    if( argc != 2 ) { return 2; }
    const std::string scenario = argv[1];
    using namespace cdda_harness;
    ui_redraw( true ); ui_begin( "inventory", "INVENTORY", "" );
    entry_type entry; entry.chosen_count = 2;
    point p( 0, 0 ); window win; int yy = 0; bool label = true, focus = true;
    if( scenario == "unmarked" ) { entry.chosen_count = 0; }
    else if( scenario == "partial" ) { entry.chosen_count = 1; }
    else if( scenario == "disabled" ) { entry.enabled = false; }
    else if( scenario == "not-multiselect" ) { multiselect = false; }
    else if( scenario == "inactive" ) { activatable_value = false; }
    else if( scenario == "nonselecting" ) { selecting = false; }
    else if( scenario == "nonitem" ) { entry.item_value = false; }
    else if( scenario == "clipped-marker" ) { p.x = -3; }
    else if( scenario == "symbols-clipped" ) { symbols = true; win.width = 4; }
    else if( scenario == "symbols-visible" ) { symbols = true; win.width = 5; }
    else if( scenario == "off-row" ) { yy = win.height; }
    else if( scenario == "omitted-label" ) { label = false; }
    else if( scenario == "unfocused" ) { focus = false; }
    else if( scenario == "topmost" ) { ui_redraw( false ); }
    else if( scenario == "duplicates" || scenario == "overflow" ) {
        const int n = scenario == "duplicates" ? 2 : 33;
        for( int i = 0; i < n; ++i ) {
            entry.chosen_count = i == n - 1 ? 2 : 0;
            draw_row( entry, p, win, yy, i == 0 );
        }
        label = false;
    } else if( scenario == "uilist" ) {
        ui_row( "item", true, "a", true, std::nullopt ); label = false;
    } else if( scenario != "marked" ) { return 2; }
    if( label || scenario == "omitted-label" ) { draw_row( entry, p, win, yy, focus, label ); }
    JsonOut out( std::cout );
    if( staged_ui ) { write_ui( out, *staged_ui ); } else { out.write_null(); }
    std::cout << '\n';
}
