"""Minimal dashboard test to debug view switching issue."""
from nicegui import ui
from rmcitecraft.config import Config

def test_minimal():
    config = Config()
    
    @ui.page("/")
    def index():
        view_container = ui.column().classes('w-full')
        
        with ui.header():
            ui.button("Home", on_click=lambda: show_home())
            ui.button("Minimal Dashboard", on_click=lambda: show_minimal_dashboard())
        
        def show_home():
            view_container.clear()
            with view_container:
                ui.label("HOME PAGE").classes('text-h3')
                ui.label("Click 'Minimal Dashboard' button above")
        
        def show_minimal_dashboard():
            view_container.clear()
            with view_container:
                ui.label("MINIMAL DASHBOARD").classes('text-h3 text-green')
                ui.label("If you see this, view switching works!")
                
        show_home()
    
    ui.run(port=8081, reload=False)

if __name__ == "__main__":
    test_minimal()
