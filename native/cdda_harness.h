#pragma once
#include <string>
#include <vector>
#include "input_enums.h"

namespace cdda_harness
{
enum class boundary_kind { normal_play, activity_poll, interrupt_confirmation, debug_prompt, menu, unsupported };
// Game-thread-only stack. Destruction restores the caller even during unwinding.
class scope
{
    public:
        explicit scope( boundary_kind kind );
        scope( const std::string &name, const std::vector<std::string> &actions );
        ~scope();
        scope( const scope & ) = delete;
        scope &operator=( const scope & ) = delete;
};
// Marks only the injected pause's native cancellation invocation.
class interrupt_owner
{
    public:
        interrupt_owner();
        ~interrupt_owner();
        interrupt_owner( const interrupt_owner & ) = delete;
        interrupt_owner &operator=( const interrupt_owner & ) = delete;
};
// Used only around the two pinned cancellation query_yn call sites.
class interrupt_query
{
    public:
        interrupt_query();
        ~interrupt_query();
        interrupt_query( const interrupt_query & ) = delete;
        interrupt_query &operator=( const interrupt_query & ) = delete;
    private:
        bool active;
};
// Marks only pinned menu owners' input waits, preserving their native keymaps.
class menu_query
{
    public:
        explicit menu_query( const std::string &category );
        ~menu_query();
        menu_query( const menu_query & ) = delete;
        menu_query &operator=( const menu_query & ) = delete;
    private:
        bool active;
};
// Called only by the pinned topmost redraw and ordinary menu renderers.
// IDs are local to this presented list, never engine/item identities.
void ui_redraw( bool top );
void ui_begin( const std::string &purpose, const std::string &category, const std::string &title );
void ui_row( const std::string &text, bool enabled, const std::string &hotkey, bool selected );
void activity_interruptible( bool value );
void playing( bool value );
void boundary();
bool poll( keyboard_mode mode, input_event &event );
void human_input();
bool enabled();
void capture_frame();
void frame_presented( bool valid );
bool write_frame( const std::string &filename );
void feed_imgui( const input_event &event );
}
