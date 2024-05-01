#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Test isometric grid math.
[x] Implement the xfms AApg and AAgp
[ ] Draw a marker at (0,0) and (N,N) to make sure the xfms are correct
[ ] Draw a rectangular prism to represent the player character
[ ] Implement keyboard movement of player character
"""

import sys
import atexit
from pathlib import Path
from dataclasses import dataclass
import random
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
    surfs['surf_game_art'] = pygame.Surface(os_window.size, flags=pygame.SRCALPHA)

    return surfs

def define_keys() -> dict:
    """Return a dict to track which unicode values are being pressed.

    These are the keys, and their Shifted versions, that continue to have
    effect while held.

    (As opposed to a key triggering only a single-shot when pressed.)
    """
    keys = {}
    keys['key_Space'] = False
    keys['key_A'] = False
    keys['key_a'] = False
    keys['key_B'] = False
    keys['key_b'] = False
    keys['key_C'] = False
    keys['key_c'] = False
    keys['key_D'] = False
    keys['key_d'] = False
    keys['key_E'] = False
    keys['key_e'] = False
    keys['key_F'] = False
    keys['key_f'] = False
    return keys

def define_colors() -> dict:
    colors = {}
    colors['color_debug_hud'] = Color(255,255,255,255)
    colors['color_game_art_bgnd'] = Color(40,40,40,255)
    colors['color_grid_lines'] =     Color(100,100,250,255)
    colors['color_vertical_lines'] = Color(150,150,250,255)
    colors['color_voxel_top'] =      Color(150,150,250,255)
    colors['color_voxel_left'] =      Color(80,80,250,255)
    colors['color_voxel_right'] =     Color(120,120,250,255)
    colors['color_grid_x_axis'] = Color(100,150,200,255)
    colors['color_grid_y_axis'] = Color(200,100,200,255)
    return colors

def define_settings() -> dict:
    settings = {}
    settings['setting_debug'] = False
    return settings

@dataclass
class LineSeg:
    start:tuple
    end:tuple

    @property
    def vector(self) -> tuple:
        return (self.end[0] - self.start[0], self.end[1] - self.start[1])

class VoxelArtwork:
    def __init__(self, game, N:int):
        self.game = game
        self.N = N
        # TODO: Move this out to a level editor later
        self.layout = self.make_random_layout()

    def make_random_layout(self) -> list:
        """Return a list of random voxels ready for rendering.

        Each item in the list is a Voxel, expressed as list [points:list, height:int].
        """
        voxel_artwork = []
        a = -1*int(self.N/2)
        b = int(self.N/2)
        # Decrement y values so that the draw order is correct for how I am
        # drawing voxels: I have to draw the ones "behind" first.
        for j in range(b,a,-1):
            for i in range(a,b):
                G = (i,j)
                height = random.choice(list(range(1,20)))
                grid_points = [(G[0]  ,G[1]  ),
                               (G[0]+1,G[1]  ),
                               (G[0]+1,G[1]+1),
                               (G[0]  ,G[1]+1)]
                voxel_artwork.append([grid_points,height])
        return voxel_artwork

    def render(self, surf) -> None:
        for voxel in self.layout:
            grid_points = voxel[0]
            height = voxel[1]
            Gs = grid_points
            Ps = [self.game.grid.xfm_gp(G) for G in grid_points]
            ### T: Top, L: Left, R: Right
            voxel_Ts = [(P[0],P[1] - height*self.game.grid.scale) for P in Ps]
            voxel_Ls = [Ps[0], Ps[1], voxel_Ts[1], voxel_Ts[0]]
            voxel_Rs = [Ps[1], Ps[2], voxel_Ts[2], voxel_Ts[1]]
            pygame.draw.polygon(surf, self.game.colors['color_voxel_top'], voxel_Ts)
            pygame.draw.polygon(surf, self.game.colors['color_voxel_left'], voxel_Ls)
            pygame.draw.polygon(surf, self.game.colors['color_voxel_right'], voxel_Rs)

class Game:
    def __init__(self):
        pygame.init()                                   # Init pygame -- quit in shutdown
        pygame.font.init()                              # Initialize the font module

        os.environ["PYGAME_BLEND_ALPHA_SDL2"] = "1"     # Use SDL2 alpha blending
        os.environ["SDL_VIDEO_WINDOW_POS"] = "1000,0"   # Position window in upper right

        self.os_window = OsWindow((60*16, 60*9))        # Track OS Window size
        logger.debug(f"Window size: {self.os_window.size[0]} x {self.os_window.size[1]}")

        self.surfs = define_surfaces(self.os_window)    # Dict of Pygame Surfaces (including pygame.display)
        pygame.display.set_caption("Isometric grid test")
        self.colors = define_colors()                   # Dict of Pygame Colors
        self.keys = define_keys()                       # Dict of which keyboard inputs are being pressed
        self.settings = define_settings()               # Dict of settings
        pygame.mouse.set_visible(False)                 # Hide the OS mouse icon

        # Game Data
        self.grid = Grid(self, N=50)
        self.voxel_artwork = VoxelArtwork(self, N=self.grid.N)

        # FPS
        self.clock = pygame.time.Clock()

    def run(self):
        while True: self.game_loop()

    def game_loop(self):
        # Create the debug HUD
        if self.settings['setting_debug']:
            self.debugHud = DebugHud(self)
        else:
            self.debugHud = None

        # Handle keyboard and mouse
        # Zoom by scrolling the mouse wheel
        # TODO: pan by pressing the mouse wheel or left-clicking
        self.handle_ui_events()

        # Clear screen
        ### fill(color, rect=None, special_flags=0) -> Rect
        self.surfs['surf_game_art'].fill(self.colors['color_game_art_bgnd'])

        # Draw grid
        self.grid.draw(self.surfs['surf_game_art'])

        # Display mouse coordinates in game grid coordinate system
        mpos_p = pygame.mouse.get_pos()                   # Mouse in pixel coord sys
        mpos_g = self.grid.xfm_pg(mpos_p)
        if self.debugHud:
            self.debugHud.add_text(f"Mouse (grid): {mpos_g}")

        self.render_mouse_location()
        # Use the power of xfm_gp()
        self.render_grid_tile_highlighted_at_mouse()
        # self.render_vertical_line_on_grid(start=(0,0))
        # self.render_vertical_line_on_grid(start=(0,0.5))
        self.voxel_artwork.render(self.surfs['surf_game_art'])

        # Display transform matrix element values a,b,c,d,e,f
        if self.debugHud:
            a,b,c,d = self.grid.scaled()
            e,f = (self.grid.e, self.grid.f)
            self.debugHud.add_text(f"a: {a:0.1f} | b: {b:0.1f} | c: {c:0.1f} | d: {d:0.1f} | e: {e:0.1f} | f: {f:0.1f}")

        # Copy game art to OS window
        ### blit(source, dest, area=None, special_flags=0) -> Rect
        self.surfs['surf_os_window'].blit(self.surfs['surf_game_art'], (0,0))

        # Display Debug HUD overlay
        if self.debugHud:
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
                case pygame.TEXTINPUT: pass
                # Handle these events
                case pygame.QUIT: sys.exit()
                case pygame.WINDOWRESIZED: self.os_window.handle_WINDOWRESIZED(event)
                case pygame.KEYDOWN: self.handle_keydown(event)
                case pygame.KEYUP: self.handle_keyup(event)
                case pygame.MOUSEWHEEL:
                    # logger.debug(event)
                    ### {'flipped': False, 'x': 0, 'y': 1, 'precise_x': 0.0, 'precise_y': 1.0, 'touch': False, 'window': None}
                    match event.y:
                        case 1: self.grid.zoom_in()
                        case -1: self.grid.zoom_out()
                        case _: pass
                case pygame.MOUSEBUTTONDOWN:
                    ### L-click: {'pos': (328, 320), 'button': 1, 'touch': False, 'window': None}
                    ### M-click: {'pos': (328, 320), 'button': 2, 'touch': False, 'window': None}
                    ### R-click: {'pos': (329, 320), 'button': 3, 'touch': False, 'window': None}
                    match event.button:
                        case 1: logger.debug("Left-click")
                        case 2: logger.debug("Middle-click")
                        case 3: logger.debug("Right-click")
                        case 4: logger.debug("Mousewheel y=+1")
                        case 5: logger.debug("Mousewheel y=-1")
                        case 6: logger.debug("Logitech G602 Thumb button 6")
                        case 7: logger.debug("Logitech G602 Thumb button 7")
                        case _: logger.debug(event)

                # Log any other events
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")
        # Randomize voxel artwork if Space is held
        if self.keys['key_Space']: self.voxel_artwork.layout = self.voxel_artwork.make_random_layout()
        # Update transform based on key presses
        # U = 20; L = -20                                 # Upper/Lower bounds
        # if self.keys['key_A']: self.grid.a = min(U, self.grid.a+1)
        # if self.keys['key_B']: self.grid.b = min(U, self.grid.b+1)
        # if self.keys['key_C']: self.grid.c = min(U, self.grid.c+1)
        # if self.keys['key_D']: self.grid.d = min(U, self.grid.d+1)
        # if self.keys['key_a']: self.grid.a = max(L, self.grid.a-1)
        # if self.keys['key_b']: self.grid.b = max(L, self.grid.b-1)
        # if self.keys['key_c']: self.grid.c = max(L, self.grid.c-1)
        # if self.keys['key_d']: self.grid.d = max(L, self.grid.d-1)
        if self.keys['key_A']: self.grid.a += 1
        if self.keys['key_B']: self.grid.b += 1
        if self.keys['key_C']: self.grid.c += 1
        if self.keys['key_D']: self.grid.d += 1
        if self.keys['key_a']: self.grid.a -= 1
        if self.keys['key_b']: self.grid.b -= 1
        if self.keys['key_c']: self.grid.c -= 1
        if self.keys['key_d']: self.grid.d -= 1
        if self.keys['key_E']: self.grid.e += 1
        if self.keys['key_e']: self.grid.e -= 1
        if self.keys['key_F']: self.grid.f += 1
        if self.keys['key_f']: self.grid.f -= 1

    def handle_keyup(self, event) -> None:
        kmod = pygame.key.get_mods()
        match event.key:
            case pygame.K_SPACE:
                self.keys['key_Space'] = False
            case pygame.K_LSHIFT:
                if self.keys['key_A']:
                    self.keys['key_A'] = False
                if self.keys['key_B']:
                    self.keys['key_B'] = False
                if self.keys['key_C']:
                    self.keys['key_C'] = False
                if self.keys['key_D']:
                    self.keys['key_D'] = False
                if self.keys['key_E']:
                    self.keys['key_E'] = False
                if self.keys['key_F']:
                    self.keys['key_F'] = False
            case pygame.K_a:
                self.keys['key_A'] = False
                self.keys['key_a'] = False
            case pygame.K_b:
                self.keys['key_B'] = False
                self.keys['key_b'] = False
            case pygame.K_c:
                self.keys['key_C'] = False
                self.keys['key_c'] = False
            case pygame.K_d:
                self.keys['key_D'] = False
                self.keys['key_d'] = False
            case pygame.K_e:
                self.keys['key_E'] = False
                self.keys['key_e'] = False
            case pygame.K_f:
                self.keys['key_F'] = False
                self.keys['key_f'] = False
            case _:
                pass

    def handle_keydown(self, event) -> None:
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
        match event.key:
            case pygame.K_q: sys.exit()                 # q - Quit
            case pygame.K_F2:                           # F2 - Toggle Debug
                self.settings['setting_debug'] = not self.settings['setting_debug']
            # TEMPORARY: Print name of keys that have no unicode representation.
            case pygame.K_RETURN: logger.debug("Return")
            case pygame.K_ESCAPE: logger.debug("Esc")
            case pygame.K_BACKSPACE: logger.debug("Backspace")
            case pygame.K_DELETE: logger.debug("Delete")
            case pygame.K_F1: logger.debug("F1")
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
            # TEMPORARY randomize voxel artwork
            case pygame.K_SPACE:
                self.keys['key_Space'] = True
            # TEMPORARY manipulate the xfm matrix
            case pygame.K_a:
                if kmod & pygame.KMOD_SHIFT:
                    self.keys['key_A'] = True
                else:
                    self.keys['key_a'] = True
            case pygame.K_b:
                if kmod & pygame.KMOD_SHIFT:
                    self.keys['key_B'] = True
                else:
                    self.keys['key_b'] = True
            case pygame.K_c:
                if kmod & pygame.KMOD_SHIFT:
                    self.keys['key_C'] = True
                else:
                    self.keys['key_c'] = True
            case pygame.K_d:
                if kmod & pygame.KMOD_SHIFT:
                    self.keys['key_D'] = True
                else:
                    self.keys['key_d'] = True
            case pygame.K_e:
                if kmod & pygame.KMOD_SHIFT:
                    self.keys['key_E'] = True
                else:
                    self.keys['key_e'] = True
            case pygame.K_f:
                if kmod & pygame.KMOD_SHIFT:
                    self.keys['key_F'] = True
                else:
                    self.keys['key_f'] = True
            case pygame.K_r:
                self.grid.reset()
            case pygame.K_z:
                if kmod & pygame.KMOD_SHIFT:
                    self.grid.zoom_in()
                else:
                    self.grid.zoom_out()
            case _:
                # Print unicode for the pressed key or key combo:
                #       'A' prints "a"        '1' prints "1"
                # 'Shift+A' prints "A"  'Shift+1' prints "!"
                logger.debug(f"{event.unicode}")

    def render_mouse_location(self) -> None:
        """Display mouse location with a white, transparent, hollow circle."""
        mpos_p = pygame.mouse.get_pos()                   # Mouse in pixel coord sys
        radius=10
        ### Surface((width, height), flags=0, Surface) -> Surface
        surf = pygame.Surface((2*radius,2*radius), flags=pygame.SRCALPHA)
        ### circle(surface, color, center, radius, width=0) -> Rect
        pygame.draw.circle(surf, Color(255,255,255,100), (radius,radius), radius, width=2)
        self.surfs['surf_game_art'].blit(surf, mpos_p, special_flags=pygame.BLEND_ALPHA_SDL2)

    def render_grid_tile_highlighted_at_mouse(self) -> None:
        """Display mouse location by highlighting the grid square the mouse is hovering over."""
        G = self.grid.xfm_pg(pygame.mouse.get_pos())
        Gs = [ # Define a square tile on the grid
                (G[0],  G[1]  ),
                (G[0]+1,G[1]  ),
                (G[0]+1,G[1]+1),
                (G[0]  ,G[1]+1)]
        points = [self.grid.xfm_gp(G) for G in Gs]
        pygame.draw.polygon(self.surfs['surf_game_art'], Color(100,255,100), points)

    def render_vertical_line_on_grid(self, start:tuple, height:int=10) -> None:
        P = self.grid.xfm_gp(start)
        l = LineSeg(start=P, end=(P[0],P[1]-(height*self.grid.scale)))
        pygame.draw.line(self.surfs['surf_game_art'], self.colors['color_vertical_lines'], l.start, l.end)

    def render_voxel_on_grid(self, grid_points:list, height:int=10) -> None:
        """
        :param grid_points:list -- list of four grid coordinates
            The intent is these coordinates are the vertices of a rectangular
            grid tile. The four coordinates are listed going clockwise around
            the rectangle starting at the "lower left" of the rectangle.
        """
        Gs = grid_points
        Ps = [self.grid.xfm_gp(G) for G in grid_points]
        ### T: Top, L: Left, R: Right
        voxel_Ts = [(P[0],P[1] - height*self.grid.scale) for P in Ps]
        voxel_Ls = [Ps[0], Ps[1], voxel_Ts[1], voxel_Ts[0]]
        voxel_Rs = [Ps[1], Ps[2], voxel_Ts[2], voxel_Ts[1]]
        pygame.draw.polygon(self.surfs['surf_game_art'], self.colors['color_voxel_top'], voxel_Ts)
        pygame.draw.polygon(self.surfs['surf_game_art'], self.colors['color_voxel_left'], voxel_Ls)
        pygame.draw.polygon(self.surfs['surf_game_art'], self.colors['color_voxel_right'], voxel_Rs)


class Grid:
    """Define a grid of lines.

    :param N:int -- number of horizontal grid lines and number of vertical grid lines
    """
    def __init__(self, game:Game, N:int):
        self.game = game                                # The Game
        self.N = N                                      # Number of grid lines
        self.scale = 1.0                                # Zoom scale
        self.reset()

    def reset(self) -> None:
        # Define a 2x3 transform matrix [a,b,e;c,d,f] to go from g (game grid) to p (pixels)
        ### Grid view is top-down (no skew: b=0, c=0)
        # self.xfm = {'a':20,'b':0,'c':0,'d':-20,'e':200,'f':300}
        # Grid view is skewed
        # self.xfm = {'a':20,'b':5,'c':0,'d':-10,'e':200,'f':300}

        # # Define 2x2 transform
        # self._a = 20
        # self._b = 5
        # self._c = 5
        # self._d = -5
        # # Define offset vector (in pixel coordinates)
        # self._e = 10
        # self._f = 300

        # Define 2x2 transform
        self._a = 8
        self._b = 7
        self._c = 3
        self._d = -5
        # Define offset vector (in pixel coordinates)
        # Place origin at center of game art
        ctr = (int(self.game.os_window.size[0]/2),
               int(self.game.os_window.size[1]/2))
        self._e = ctr[0]
        self._f = ctr[1]

    @property
    def a(self) -> float:
        return self._a
    @a.setter
    def a(self, value) -> float:
        self._a = value

    @property
    def b(self) -> float:
        return self._b
    @b.setter
    def b(self, value) -> float:
        self._b = value

    @property
    def c(self) -> float:
        return self._c
    @c.setter
    def c(self, value) -> float:
        self._c = value

    @property
    def d(self) -> float:
        return self._d
    @d.setter
    def d(self, value) -> float:
        self._d = value

    @property
    def e(self) -> float:
        return self._e
    @e.setter
    def e(self, value) -> float:
        self._e = value

    @property
    def f(self) -> float:
        return self._f
    @f.setter
    def f(self, value) -> float:
        self._f = value

    def scaled(self) -> tuple:
        return (self.a*self.scale, self.b*self.scale, self.c*self.scale, self.d*self.scale)

    @property
    def det(self) -> float:
        a,b,c,d = self.scaled()
        det = a*d-b*c
        if det == 0:
            # If det=0, Ainv will have div by 0, so just make det very small.
            return 0.0001
        else:
            return a*d-b*c

    @property
    def hlinesegs(self) -> list:
        """Return list of horizontal line segments."""
        ### Put origin in bottom left
        # a = 0                                         # Bottom/Left of grid
        # b = self.N                                    # Top/Right of grid
        ### Put origin in center
        a = -1*int(self.N/2)                            # Bottom/Left of grid
        b = int(self.N/2)                               # Top/Right of grid
        cs = list(range(a,b+1))
        hls = []
        for c in cs:
            hls.append (LineSeg(start=(a,c),end=(b,c)))
        return hls

    @property
    def vlinesegs(self) -> list:
        """Return list of vertical line segments."""
        ### Put origin in bottom left
        # a = 0                                           # Bottom/Left of grid
        # b = self.N                                      # Top/Right of grid
        ### Put origin in center
        a = -1*int(self.N/2)                            # Bottom/Left of grid
        b = int(self.N/2)                               # Top/Right of grid
        cs = list(range(a,b+1))                         # Intermediate points
        vls = []
        for c in cs:
            vls.append (LineSeg(start=(c,a),end=(c,b)))
        return vls

    def xfm_gp(self, point:tuple) -> tuple:
        """Transform point from game grid coordinates to OS Window pixel coordinates."""
        # Define 2x2 transform
        a,b,c,d = self.scaled()
        # Define offset vector (in pixel coordinates)
        e,f = (self.e, self.f)
        return (a*point[0] + b*point[1] + e, c*point[0] + d*point[1] + f)

    def xfm_pg(self, point:tuple, p:int=0) -> tuple:
        """Transform point from OS Window pixel coordinates to game grid coordinates.

        :param point:tuple -- (x,y) in pixel coordinates
        :param p:int -- decimal precision of returned coordinate (default: 0, return ints)
        :return tuple -- (x,y) in grid goordinates
        """
        # Define 2x2 transform
        a,b,c,d = self.scaled()
        # Define offset vector (in pixel coordinates)
        e,f = (self.e, self.f)
        # Calculate the determinant of the 2x2
        det = self.det
        g = ((   d/det)*point[0] + (-1*b/det)*point[1] + (b*f-d*e)/det,
             (-1*c/det)*point[0] + (   a/det)*point[1] + (c*e-a*f)/det)
        # Define precision
        if p==0:
            return (int(round(g[0])), int(round(g[1])))
        else:
            return (round(g[0],p), round(g[1],p))

    def zoom_in(self) -> None:
        self.scale *= 1.1

    def zoom_out(self) -> None:
        self.scale *= 0.9

    def draw(self, surf:pygame.Surface) -> None:
        linesegs = self.hlinesegs + self.vlinesegs
        for grid_line in linesegs:
            if self.game.settings['setting_debug']:
                # Set color to be a gradient from lower left to upper right of blue to red
                if (grid_line.start[0] == 0) and (grid_line.end[0] == 0):
                    color = Color(self.game.colors['color_grid_x_axis'])
                elif (grid_line.start[1] == 0) and (grid_line.end[1] == 0):
                    color = Color(self.game.colors['color_grid_y_axis'])
                else:
                    color = Color(self.game.colors['color_grid_lines'])
                    if (grid_line.start[0] == grid_line.end[0]):
                        # Vertical lines get more red from left to right
                        color.r = min(255, 155 + 2*int(grid_line.start[0]))
                    elif (grid_line.start[1] == grid_line.end[1]):
                        # Horizontal lines get more red from top to bottom
                        color.r = min(255, 155 + 2*int(grid_line.start[1]))
            else:
                color = Color(self.game.colors['color_grid_lines'])
            ### Drawing anti-aliased lines vs not anti-aliased seems to have no effect on framerate.
            ### Not anti-aliased:
            ### line(surface, color, start_pos, end_pos, width=1) -> Rect
            if self.game.settings['setting_debug']:
                # Draw x and y axis thicker and a different color from the rest of the grid
                if ((grid_line.start[0] == 0) and (grid_line.end[0] == 0)) or ((grid_line.start[1] == 0) and (grid_line.end[1] == 0)):
                    pygame.draw.line( surf, color,
                            self.xfm_gp(grid_line.start),
                            self.xfm_gp(grid_line.end),
                            width=2
                            )
            ### Anti-aliased:
            ### aaline(surface, color, start_pos, end_pos, blend=1) -> Rect
            ### Blend is 0 or 1. Both are anti-aliased.
            ### 1: (this is what you want) blend with the surface's existing pixel color
            ### 0: completely overwrite the pixel (as if blending with black)
            pygame.draw.aaline(surf, color,
                    self.xfm_gp(grid_line.start),
                    self.xfm_gp(grid_line.end),
                    blend=1                             # 0 or 1
                    )

if __name__ == '__main__':
    atexit.register(shutdown)                           # Safe shutdown
    logger = setup_logging()
    print(f"Run {Path(__file__).name}")
    Game().run()

