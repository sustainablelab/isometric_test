#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Test isometric grid math.
"""

import sys
import atexit
from pathlib import Path
from dataclasses import dataclass
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color
from libs.utils import setup_logging, DebugHud, OsWindow

def shutdown() -> None:
    if logger: logger.info("Shutdown")
    # Clean up pygame
    pygame.font.quit()                                  # Uninitialize the font module
    pygame.quit()                                       # Uninitialize all pygame modules
    pygame.display.set_caption("Isometric grid test")

def define_surfaces(os_window:OsWindow) -> dict:
    """Return dictionary of pygame Surfaces.

    :param os_window:OsWindow -- defines OS Window 'size' and 'flags'
    :return dict -- {'surf_name': pygame.Surface, ...}
    """
    surfs = {}                                      # Dict of Pygame Surfaces

    # The first surface is the OS Window. Initialize the window for display.
    ### set_mode(size=(0, 0), flags=0, depth=0, display=0, vsync=0) -> Surface
    surfs['surf_os_window'] = pygame.display.set_mode(os_window.size, os_window.flags)

    # Blend artwork on the game art surface.
    # This is the final surface that is  copied to the OS Window.
    surfs['surf_game_art'] = pygame.Surface(os_window.size)

    return surfs

def define_colors() -> dict:
    colors = {}
    colors['color_debug_hud'] = Color(255,255,255,255)
    colors['color_game_art_bgnd'] = Color(40,40,40,255)
    colors['color_grid_lines'] = Color(100,100,200,255)
    return colors

@dataclass
class LineSeg:
    start:tuple
    end:tuple

    @property
    def vector(self) -> tuple:
        return (self.end[0] - self.start[0], self.end[1] - self.start[1])

class Game:
    def __init__(self):
        pygame.init()                                   # Init pygame -- quit in shutdown
        pygame.font.init()                              # Initialize the font module

        os.environ["PYGAME_BLEND_ALPHA_SDL2"] = "1"     # Use SDL2 alpha blending
        os.environ["SDL_VIDEO_WINDOW_POS"] = "1000,0"   # Position window in upper right

        self.os_window = OsWindow((60*16, 60*9))        # Track OS Window size
        logger.debug(f"Window size: {self.os_window.size[0]} x {self.os_window.size[1]}")

        self.surfs = define_surfaces(self.os_window)    # Dict of Pygame Surfaces
        self.colors = define_colors()                   # Dict of Pygame Colors

        self.debugHud = None                            # HUD created in game_loop()

        # Game Data
        self.grid = Grid(self, N=10)

        # FPS
        self.clock = pygame.time.Clock()

    def run(self):
        while True: self.game_loop()

    def game_loop(self):
        # Create the debug HUD
        self.debugHud = DebugHud(self)

        # Handle keyboard and mouse
        self.handle_ui_events()

        # Clear screen
        ### fill(color, rect=None, special_flags=0) -> Rect
        self.surfs['surf_game_art'].fill(self.colors['color_game_art_bgnd'])

        # Draw grid
        self.grid.draw(self.surfs['surf_game_art'])

        # Display mouse coordinates in game grid coordinate system
        mpos_p = pygame.mouse.get_pos()                   # Mouse in pixel coord sys
        mpos_g = self.grid.xfm_pg(mpos_p)
        self.debugHud.add_text(f"Mouse (grid): {mpos_g}")

        # Copy game art to OS window
        ### blit(source, dest, area=None, special_flags=0) -> Rect
        self.surfs['surf_os_window'].blit(self.surfs['surf_game_art'], (0,0))

        # Display Debug HUD overlay
        self.debugHud.render(self.colors['color_debug_hud'])

        # Draw to the OS window
        pygame.display.update()

        ### clock.tick(framerate=0) -> milliseconds
        self.clock.tick(60)

    def handle_ui_events(self) -> None:
        for event in pygame.event.get():
            match event.type:
                # No use for these events yet
                case pygame.AUDIODEVICEADDED: pass
                case pygame.ACTIVEEVENT: pass
                case pygame.MOUSEMOTION: pass
                case pygame.WINDOWENTER: pass
                case pygame.WINDOWLEAVE: pass
                case pygame.WINDOWEXPOSED: pass
                case pygame.VIDEOEXPOSE: pass
                case pygame.WINDOWHIDDEN: pass
                case pygame.WINDOWMOVED: pass
                case pygame.WINDOWSHOWN: pass
                case pygame.WINDOWFOCUSGAINED: pass
                case pygame.WINDOWTAKEFOCUS: pass
                case pygame.KEYUP: pass
                case pygame.TEXTINPUT: pass
                # Handle these events
                case pygame.QUIT: sys.exit()
                case pygame.WINDOWRESIZED: self.os_window.handle_WINDOWRESIZED(event)
                case pygame.KEYDOWN: self.handle_keydown(event)
                # Log any other events
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")

    def handle_keydown(self, event) -> None:
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
        match event.key:
            case pygame.K_q: sys.exit()                 # q - Quit
            # TEMPORARY: Print name of keys that have no unicode representation.
            case pygame.K_SPACE: logger.debug("Space")
            case pygame.K_RETURN: logger.debug("Return")
            case pygame.K_ESCAPE: logger.debug("Esc")
            case pygame.K_BACKSPACE: logger.debug("Backspace")
            case pygame.K_DELETE: logger.debug("Delete")
            case pygame.K_F1: logger.debug("F1")
            case pygame.K_F2: logger.debug("F2")
            case pygame.K_F3: logger.debug("F3")
            case pygame.K_F4: logger.debug("F4")
            case pygame.K_F5: logger.debug("F5")
            case pygame.K_F6: logger.debug("F6")
            case pygame.K_F7: logger.debug("F7")
            case pygame.K_F8: logger.debug("F8")
            case pygame.K_F9: logger.debug("F9")
            case pygame.K_F10: logger.debug("F10")
            case pygame.K_F11: logger.debug("F11")
            case pygame.K_F12: logger.debug("F12")
            case pygame.K_LSHIFT: logger.debug("Left Shift")
            case pygame.K_RSHIFT: logger.debug("Right Shift")
            case pygame.K_LALT: logger.debug("Left Alt")
            case pygame.K_RALT: logger.debug("Right Alt")
            case pygame.K_LCTRL: logger.debug("Left Ctrl")
            case pygame.K_RCTRL: logger.debug("Right Ctrl")
            case _:
                # Print unicode for the pressed key or key combo:
                #       'A' prints "a"        '1' prints "1"
                # 'Shift+A' prints "A"  'Shift+1' prints "!"
                logger.debug(f"{event.unicode}")

class Grid:
    """Define a grid of lines.

    :param N:int -- number of horizontal grid lines and number of vertical grid lines
    """
    def __init__(self, game:Game, N:int):
        self.game = game                                # The Game
        self.N = N                                      # Number of grid lines

        # Define a 2x3 transform matrix [a,b,e;c,d,f] to go from g (game grid) to p (pixels)
        # self.xfm = {'a':20,'b':0,'c':0,'d':-20,'e':200,'f':300}
        # TODO: Why is the mouse grid coordinate wrong when I skew the grid?
        self.xfm = {'a':20,'b':5,'c':0,'d':-10,'e':200,'f':300}

    @property
    def det(self) -> float:
        a=self.xfm['a']
        b=self.xfm['b']
        c=self.xfm['c']
        d=self.xfm['d']
        return a*d-b*c

    @property
    def hlinesegs(self) -> list:
        """Return list of horizontal line segments."""
        a = 0                                           # Bottom/Left of grid
        b = self.N                                      # Top/Right of grid
        cs = list(range(a,b+1))
        hls = []
        for c in cs:
            hls.append (LineSeg(start=(a,c),end=(b,c)))
        return hls

    @property
    def vlinesegs(self) -> list:
        """Return list of vertical line segments."""
        a = 0                                           # Bottom/Left of grid
        b = self.N                                      # Top/Right of grid
        cs = list(range(a,b+1))                         # Intermediate points
        vls = []
        for c in cs:
            vls.append (LineSeg(start=(c,a),end=(c,b)))
        return vls

    def xfm_gp(self, point:tuple) -> tuple:
        """Transform point from game grid coordinates to OS Window pixel coordinates."""
        # Define 2x2 transform
        a=self.xfm['a']
        b=self.xfm['b']
        c=self.xfm['c']
        d=self.xfm['d']
        # Define offset vector (in pixel coordinates)
        e=self.xfm['e']
        f=self.xfm['f']
        return (a*point[0] + b*point[1] + e, c*point[0] + d*point[1] + f)

    def xfm_pg(self, point:tuple) -> tuple:
        """Transform point from OS Window pixel coordinates to game grid coordinates."""
        # Define 2x2 transform
        a=self.xfm['d']
        b=self.xfm['b']
        c=self.xfm['c']
        d=self.xfm['d']
        # Define offset vector (in pixel coordinates)
        e=self.xfm['e']
        f=self.xfm['f']
        # Calculate the determinant of the 2x2
        det = self.det
        g = ((   d/det)*point[0] + (-1*b/det)*point[1] + (b*f-d*e)/det,
             (-1*c/det)*point[0] + (   a/det)*point[1] + (c*e-a*f)/det)
        # Define precision
        p = 0
        if p==0:
            return (int(round(g[0])), int(round(g[1])))
        else:
            return (round(g[0],p), round(g[1],p))

    def draw(self, surf:pygame.Surface) -> None:
        linesegs = self.hlinesegs + self.vlinesegs
        for grid_line in linesegs:
            ### line(surface, color, start_pos, end_pos, width=1) -> Rect
            pygame.draw.line(
                    surf,
                    self.game.colors['color_grid_lines'],
                    self.xfm_gp(grid_line.start),
                    self.xfm_gp(grid_line.end)
                    )

if __name__ == '__main__':
    atexit.register(shutdown)                           # Safe shutdown
    logger = setup_logging()
    print(f"Run {Path(__file__).name}")
    Game().run()

