#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Test isometric grid math.
[x] Implement the xfms AApg and AAgp
[x] Draw a marker at (0,0) and (N,N) to make sure the xfms are correct
[x] Draw some placeholder wireframe art to represent the player character
[x] Implement keyboard movement of player character
[x] Collision detection between player and walls
[x] Add gravity to player
[x] Add player levitation (infinite jump)
[x] Draw a shadow under the player
[x] Refactor: pull logic out of rendering
    * Rendering should only be responsible for draw order!
    * Calculate info necessary for rendering before the one big render call
    * Example:
        * in its current state, I cannot render the mouse cursor "under" the
        player without also putting it "under" the voxel that the player is
        standing on
    [x] Refactor TileMap to be a dict of grid locations rather than a list of walls
    [x] Refactor VoxelArtwork to describe voxels as dicts rather than lists
        * Ah, but I still need a list to iterate over for draw-order.
    [x] Player renders on top of yellow highlight when mouse hovers at the voxel the player is standing on
[x] Draw steps
[x] Zoom to fit
[x] Pan
[x] Fullscreen
[ ] Add controls for moving in discrete steps:
    [x] arrow keys and w,a,s,d become what h,j,k,l are now -- free movement
        [ ] But end free movement on a tile: continue movement until character is on a tile
    [x] h,j,k,l become moving to discrete tiles
        [ ] if the player is not on a discrete tile, this key puts them onto one
        [ ] nudge the character -- change Shift+h,j,k,l to Alt+h,j,k,l-- this
            is just for dev so I have a way to nudge the character without
            collision detection rules 
    [ ] Apply collision detection to discrete movement
[ ] Refactor collision detection out to its own section
    [x] use keys dict to set a moves dict
    [ ] then handle collision detection in its own function that just uses the moves dict

[x] Draw a floor
    [ ] Give floor same color gradient effect that I put on the grid
[x] Add a Help HUD
[x] If Debug HUD is visible, show Help HUD below Debug HUD
[ ] Save game data
[ ] Load game data
[ ] Improved collision detection using height:
    * Player traverses small height differences
    * Player is only blocked when height difference exceeds some amount
    * [x] Let mouse highlight "top" of a wall
    * [x] Left-click places player on "top" of a wall
    * [x] Player stays on top of the wall instead of falling through
    * [x] Player shadow is on the voxel (if any) under the player
    * [x] Player can walk off a wall
    * [x] Player can walk on a wall (need to consider height difference in collision detection)
    * [x] Player can walk up and down steps
[ ] Include spell casting
    * [x] ':' to start spell casting
    * [x] keystrokes appear at bottom of screen
    * [x] romanized chars appear above character's head
    * [x] adjust size of romanized chars
    * [ ] Fix romanized chars location -- center above player's head
    * [ ] start a newline if romanized chars extend too far
    * [ ] make color of romanized chars adjustable
    * [ ] add more characters (Kurt added letter 'z')
"""

import sys
import atexit
from pathlib import Path
from dataclasses import dataclass
import random
import json
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color
from libs.utils import setup_logging, load_image, OsWindow, Text, DebugHud, HelpHud

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

    # Temporary drawing surface -- draw on this, blit the drawn portion, then clear this.
    surfs['surf_draw'] = pygame.Surface(surfs['surf_game_art'].get_size(), flags=pygame.SRCALPHA)

    # This surface is populated later when Game instantiates RomanizedChars
    surfs['surf_romanized_chars'] = None

    return surfs

def define_actions() -> dict:
    actions = {}
    actions['action_levitate'] = False
    return actions

def define_moves() -> dict:
    moves = {}
    # Free movement
    moves['move_down']  = False
    moves['move_up']    = False
    moves['move_right'] = False
    moves['move_left']  = False
    # Discrete movement
    moves['move_down_to_tile']  = False
    moves['move_up_to_tile']    = False
    moves['move_right_to_tile'] = False
    moves['move_left_to_tile']  = False
    return moves

def define_held_keys() -> dict:
    """Return a dict to track which keys are held down.

    These are the keys, and their Shifted versions, that continue to have
    effect while held.

    (As opposed to a key triggering only a single-shot when pressed.)
    """
    keys = {}
    # Special
    keys['key_Space'] = False
    keys['key_Shift_Space'] = False
    # Xfm matrix
    keys['key_A'] = False
    # keys['key_a'] = False # Repurposed
    keys['key_B'] = False
    keys['key_b'] = False
    keys['key_C'] = False
    keys['key_c'] = False
    keys['key_D'] = False
    # keys['key_d'] = False # Repurposed
    keys['key_E'] = False
    keys['key_e'] = False
    keys['key_F'] = False
    keys['key_f'] = False
    # Discrete Movement
    keys['key_j'] = False
    keys['key_k'] = False
    keys['key_h'] = False
    keys['key_l'] = False
    # Free Movement
    keys['key_s'] = False
    keys['key_w'] = False
    keys['key_a'] = False
    keys['key_d'] = False
    return keys

def define_colors() -> dict:
    colors = {}
    colors['color_clear'] = Color(0,0,0,0)
    colors['color_debug_hud'] = Color(255,255,255,255)
    colors['color_help_hud'] = Color(200,150,100,255)
    # colors['color_debug_keystrokes'] = Color(80,130,80)
    colors['color_debug_keystrokes'] = Color(200,200,200)
    colors['color_game_art_bgnd'] = Color(40,40,40,255)
    colors['color_grid_lines'] =     Color(100,100,250,255)
    colors['color_vertical_lines'] = Color(150,150,250,255)
    colors['color_voxel_top'] =      Color(150,150,250,255)
    colors['color_voxel_left'] =      Color(80,80,250,255)
    colors['color_voxel_right'] =     Color(120,120,250,255)
    colors['color_grid_x_axis'] = Color(100,150,200,255)
    colors['color_grid_y_axis'] = Color(200,100,200,255)
    colors['color_floor_solid'] = Color(70,40,130)
    floor = colors['color_floor_solid']
    colors['color_floor_shadow'] = Color(floor.r-20, floor.g-20, floor.b-40)
    colors['color_floor_shadow_light'] = Color(floor.r-5, floor.g-5, floor.b-10)
    return colors

def define_settings() -> dict:
    settings = {}
    settings['setting_show_help'] = True
    settings['setting_debug'] = False
    return settings

@dataclass
class LineSeg:
    start:tuple
    end:tuple

    @property
    def vector(self) -> tuple:
        return (self.end[0] - self.start[0], self.end[1] - self.start[1])

@dataclass
class Wall:
    """A wall is a list [points:list, height:int].

    Each point is the "lower-left" grid coordinate of that bit of wall.

    >>> wall = Wall(points=[(i,-2) for i in range(-2,2)], height=25)
    >>> print(wall)
    Wall(points=[(-2, -2), (-1, -2), (0, -2), (1, -2)], height=25)
    """
    points:list
    height:int
    # style:str = "style_shade_faces_solid_color"
    style:str = "style_skeleton_frame"

class Player:
    def __init__(self, game):
        self.game = game
        self.pos = (9.0,2.0)
        self.height = 10
        self.speed_walk = 0.2
        self.speed_rise = 3.0
        self.wiggle = 0.1                               # Amount to randomize each coordinate value
        self.moving = False
        # TODO: sign of z-direction always confuses me, e.g., look at self.z in render_romanized_chars
        self.z = 0                                      # Position in z-direction
        self.zclimbmax = 3.5                            # Max amt player can climb -- determines max height of steps
        self.dz = 0                                     # Speed in z-direction
        self.voxel = None                               # The voxel at the player's location (e.g., standing on a wall)
        self.is_casting = False
        self.spell = ""
        self.keystrokes = ""

    def update_voxel(self) -> None:
        """Figure out which voxel (if any) is below the player."""
        G = (int(self.pos[0]), int(self.pos[1]))
        tiles = self.game.tile_map.layout
        voxels = self.game.voxel_artwork.layout
        if G in tiles:
            self.voxel = voxels[G]
        else:
            self.voxel = None # Nothing under the player

    def old_update_voxel(self) -> None:
        """Figure out which voxel (if any) is below the player."""
        self.voxel = None  # Assume nothing under the player
        G = (int(self.pos[0]), int(self.pos[1]))
        for voxel in self.game.voxel_artwork.layout:
            grid_points = voxel[0]
            height = voxel[1]
            if G == grid_points[0]:
                self.voxel = voxel

    def render(self, surf:pygame.Surface) -> None:
        """Display the player."""
        if self.moving:
            # Wiggle more if moving
            self.wiggle = 0.5
        else:
            # Wiggle less if standing still
            self.wiggle = 0.2
        G = self.pos
        percentage = 0.5                                # Player fills half the tile
        p = 1-percentage
        d = p/2
        Gs = [ # Define a polygon on the grid
              (G[0] + d     + random.uniform(-1*self.wiggle*d, self.wiggle*d), G[1] + d    + random.uniform(-1*self.wiggle*d, self.wiggle*d)),
              (G[0] + 1 - d + random.uniform(-1*self.wiggle*d, self.wiggle*d), G[1] + d    + random.uniform(-1*self.wiggle*d, self.wiggle*d)),
              (G[0] + 1 - d + random.uniform(-1*self.wiggle*d, self.wiggle*d), G[1] + 1 -d + random.uniform(-1*self.wiggle*d, self.wiggle*d)),
              (G[0] + d     + random.uniform(-1*self.wiggle*d, self.wiggle*d), G[1] + 1 -d + random.uniform(-1*self.wiggle*d, self.wiggle*d))]
        # Draw player shadow -- QUICK AND DIRTY LIGHTING -- this shadow effect is terrible
        # TEMPORARY: assume shadow is on floor at z=0
        # Check actual z-value of what is below player and set 'floor_height' to that
        floor_height = 0
        if self.voxel != None:
            floor_height = -1*self.voxel['height']*self.game.grid.scale
        ### Grow light shadow proportional to height above floor_height
        k = 0.005*(floor_height - self.z)
        shadow_light_points_g = [
                (Gs[0][0] - k, Gs[0][1] - k),
                (Gs[1][0] + k, Gs[1][1] - k),
                (Gs[2][0] + k, Gs[2][1] + k),
                (Gs[3][0] - k, Gs[3][1] + k)]
        ### TODO: Clip light shadow if neighboring tile is occupied
        # pos = self.pos
        # neighbors = [
        #         (int(pos[0]) - 1, int(pos[1]) - 1),
        #         (int(pos[0]) - 1, int(pos[1]) + 0),
        #         (int(pos[0]) - 1, int(pos[1]) + 1),
        #         (int(pos[0]) + 0, int(pos[1]) - 1),
        #         (int(pos[0]) + 0, int(pos[1]) + 1),
        #         (int(pos[0]) + 1, int(pos[1]) - 1),
        #         (int(pos[0]) + 1, int(pos[1]) + 0),
        #         (int(pos[0]) + 1, int(pos[1]) + 1),
        #         ]
        # for point in shadow_light_points_g:
        #     if (int(point[0]),int(point[1])) in neighbors:
        #         point = (int(point[0]),int(point[1]))

        ### Shrink dark shadow proportional to height above floor_height
        # Center of tile
        # TODO: if moving, push center (player head) in direction of motion
        Gc =  (G[0] + 0.5   + random.uniform(-1*self.wiggle*d, self.wiggle*d), G[1] + 0.5  + random.uniform(-1*self.wiggle*d, self.wiggle*d))
        # k = min(0.5,0.005*(abs(floor_height - self.z)))
        k = min(0.25, abs(0.5 - 0.005*(floor_height - self.z)))
        shadow_dark_points_g = [
                (Gc[0] - k, Gc[1] - k),
                (Gc[0] + k, Gc[1] - k),
                (Gc[0] + k, Gc[1] + k),
                (Gc[0] - k, Gc[1] + k)]
        # Convert to pixel coordinates
        points = [self.game.grid.xfm_gp(G) for G in Gs]
        Pc = self.game.grid.xfm_gp(Gc)
        shadow_light_points_p_z0 = [self.game.grid.xfm_gp(G) for G in shadow_light_points_g]
        shadow_dark_points_p_z0 = [self.game.grid.xfm_gp(G) for G in shadow_dark_points_g]
        # Bring the shadow up to the floor height
        shadow_light_points_p = [(P[0],P[1]+floor_height) for P in shadow_light_points_p_z0]
        shadow_dark_points_p  = [(P[0],P[1]+floor_height) for P in shadow_dark_points_p_z0]
        pygame.draw.polygon(surf, self.game.colors['color_floor_shadow_light'], shadow_light_points_p)
        pygame.draw.polygon(surf, self.game.colors['color_floor_shadow'], shadow_dark_points_p)
        # Incorporate player height:
        points = [(p[0],p[1] + self.z) for p in points]
        Pc = (Pc[0], Pc[1] + self.z)
        # Elevate that center point
        center = (Pc[0], Pc[1] - self.height*self.game.grid.scale)
        # Draw player dress
        ### polygon(surface, color, points) -> Rect
        color = Color(self.game.colors['color_grid_y_axis'])
        pygame.draw.polygon(surf, color, [points[1],points[2],center])
        color.r -= 50; color.g -=50; color.b -= 50
        pygame.draw.polygon(surf, color, [points[0],points[1],center])
        # Draw sketchy lines around player
        ### line(surface, color, start_pos, end_pos) -> Rect
        for p in points:
            pygame.draw.line(surf, self.game.colors['color_grid_y_axis'], p, center, width=2)
        # Draw player head
        ### circle(surface, color, center, radius, width=0, draw_top_right=None, draw_top_left=None, draw_bottom_left=None, draw_bottom_right=None) -> Rect
        pygame.draw.circle(surf, Color(0,0,0), center, 2*self.game.grid.scale)

    def render_romanized_chars(self, surf:pygame.Surface) -> None:
        """Render romanized chars above the player's head.

        :param surf:pygame.Surface -- render to this surface (probably 'surf_game_art')

        The chars are already scaled when RomanizedChars is instantiated.
        """
        # Get the number of chars to render
        nchars = 0
        for letter in self.keystrokes:
            if letter in self.game.romanized_chars.letters:
                nchars += 1
        
        # TODO: store player center, not player lower left!
        # pos = self.game.grid.xfm_gp(self.pos)           # FUTURE: Convert player pos to pixel coordinates
        pos = self.game.grid.xfm_gp((self.pos[0]+0.5, self.pos[1]+0.5))  # HACK: Convert player pos to pixel coordinates
        # debug_nchars = Text((0,0), font_size=20, sys_font="Roboto Mono")
        # debug_nchars.update(str(nchars))
        # text_size = debug_nchars.font.size(debug_nchars.text_lines[0])
        # logger.debug(f"text_size: {text_size}")
        text_size = (nchars*self.game.romanized_chars.size[0], self.game.romanized_chars.size[1])
        pos = (pos[0] - text_size[0]/2, pos[1] - text_size[1] - (self.height + 3) *self.game.grid.scale + self.z)
        # debug_nchars.pos = pos
        # debug_nchars.render(surf, Color(255,255,255))

        offset = (0,0)                                  # Track position for next letter
        for letter in self.keystrokes:
            if letter in self.game.romanized_chars.letters:
                index = self.game.romanized_chars.letters[letter]
                surf.blit(self.game.surfs['surf_romanized_chars'],
                          (pos[0]+offset[0], pos[1]+offset[1]),
                          area=pygame.Rect(
                              (index*self.game.romanized_chars.size[0],0),
                              self.game.romanized_chars.size
                              ))
                offset = (offset[0]+self.game.romanized_chars.size[0], offset[1])

    def old_render_romanized_chars(self, surf:pygame.Surface) -> None:
        """Render romanized chars above the player's head.

        This is the old version because I attempted to do the scaling here.
        I couldn't get the text to center after I scaled it.
        """
        # Get the number of chars to render
        nchars = 0
        for letter in self.keystrokes:
            if letter in self.game.romanized_chars.letters:
                nchars += 1

        # Get the width and height of the complete image for all keystrokes thus far
        img_w = nchars*self.game.romanized_chars.size[0]
        img_h = self.game.romanized_chars.size[1]

        # TODO: Scale the image
        k = 0.5
        scaled_img_w = img_w*k
        scaled_img_h = img_h*k

        # Position the chars centered above the player's head
        pos = self.game.grid.xfm_gp(self.pos)           #  Convert player pos to pixel coordinates
        start = (pos[0] - img_w/2, pos[1] - img_h - self.height*self.game.grid.scale)
        # start = (pos[0] - scaled_img_w/2, pos[1] - scaled_img_h - self.height*self.game.grid.scale)

        offset = (0,0)                                  # Offset next letter from start position
        for letter in self.keystrokes:
            if letter in self.game.romanized_chars.letters:
                # Look up index of this letter
                index = self.game.romanized_chars.letters[letter]
                # Blit letter art at that index
                ### blit(source, dest, area=None, special_flags=0) -> Rect
                # surf.blit(self.game.surfs['surf_romanized_chars'],
                self.game.surfs['surf_draw'].blit(self.game.surfs['surf_romanized_chars'],
                    (start[0] + offset[0], start[1] + offset[1]),
                    area=pygame.Rect(
                        (index*self.game.romanized_chars.size[0],0),
                        self.game.romanized_chars.size
                        ))
                # Increment x-position for next letter
                offset = (offset[0]+self.game.romanized_chars.size[0], offset[1])

        # Create a new (smaller) surface
        size = self.game.surfs['surf_draw'].get_size()
        size = (size[0]*k, size[1]*k)
        surf_chars = pygame.Surface(size, flags=pygame.SRCALPHA)
        # Copy and scale temporary drawing surface to new surface
        smooth = True  # I can't tell a difference in smoothness or performance
        if smooth:
            ### smoothscale(surface, size, dest_surface=None) -> Surface
            pygame.transform.smoothscale(self.game.surfs['surf_draw'], size, surf_chars)
        else:
            ### scale(surface, size, dest_surface=None) -> Surface
            pygame.transform.scale(self.game.surfs['surf_draw'], size, surf_chars)

        # Clean the temporary drawing surface
        rect = pygame.Rect( (start[0] - img_w/2, start[1] - img_h/2),
                            (start[0] + img_w/2, start[1] + img_h/2))
        self.game.surfs['surf_draw'].fill(self.game.colors['color_clear'], rect=rect)

        # Scale area rect by k to match scaling of the temporary drawing surface
        # rect = pygame.Rect( (k*(start[0] - img_w/2), k*(start[1] - img_h/2)),
        #                     (k*(start[0] + img_w/2), k*(start[1] + img_h/2)))
        rect = pygame.Rect( (start[0] - scaled_img_w/2, start[1] - scaled_img_h/2),
                            (start[0] + scaled_img_w/2, start[1] + scaled_img_h/2))

        # Blit to game art
        surf.blit(surf_chars, # self.game.surfs['surf_draw'],
                    (start[0] - img_w/2, start[1] - img_h/2),
                    area=rect,
                    special_flags=pygame.BLEND_ALPHA_SDL2
                  )


# TODO: Move this out to a level editor later
class TileMap:
    """A square layout of items in grid coordinates.

    :param N:int -- length of grid (grid is NxN)

    Attributes
    N:int -- grid is NxN
    a:int -- lower left of layout is grid coordinate (a,a)
    b:int -- lower left of layout is grid coordinate (b,b)
    layout:dict --  keys are the grid coordinate of the lower-left of the grid tile
                    values are a dict describing the tile

    Old attributes
    walls:list -- list of walls, each wall is a list of voxels, each voxel has a pos, height, and style
    """
    def __init__(self, N:int):
        self.N = N
        self.a = -1*int(self.N/2)
        self.b = int(self.N/2)

        # Make a layout of walls
        a = self.a
        b = self.b

        # Create a layout (TODO: move this to a level editor/generator)
        layout = {}

        if 0:
            ### Example making a single voxel wall in the center of the grid
            layout[(0,0)] = {'height':25, 'style':"style_shade_faces_solid_color", 'rand_amt':5}

        elif 0:
            ### Example making a staircase
            step_height = 0
            for i in range(20):
                step_height += 3
                layout[(0,i)] = {'height':step_height, 'style':"style_shade_faces_solid_color", 'rand_amt':0}

        else:
            ### Make walls
            # Outer walls
            for i in range(a,b):
                layout[(i,  a)]   = {'height':25, 'style':"style_shade_faces_solid_color", 'rand_amt':5} # Front left wall
                layout[(i,  b-1)] = {'height':65, 'style':"style_shade_faces_solid_color", 'rand_amt':5} # Back right wall
                layout[(a,  i)]   = {'height':65, 'style':"style_shade_faces_solid_color", 'rand_amt':5} # Back left wall
                layout[(b-1,i)]   = {'height':25, 'style':"style_skeleton_frame", 'rand_amt':5} # Front right wall
            # Inner walls: walls at constant x from y=a to y=b and constant y from x=a to x=b
            x = -10; a = -10; b = 20
            for i in range(a,b):
                layout[(x,i)] = {'height':5, 'style':"style_shade_faces_solid_color", 'rand_amt':5}
            y = 20; a = -10; b = 20
            for i in range(a,b):
                layout[(i,y)] = {'height':5, 'style':"style_shade_faces_solid_color", 'rand_amt':5}
            x = -5; a = -10; b = 15
            for i in range(a,b):
                layout[(x,i)] = {'height':5, 'style':"style_shade_faces_solid_color", 'rand_amt':5}
            y = 15; a = -5; b = 20
            for i in range(a,b):
                layout[(i,y)] = {'height':5, 'style':"style_shade_faces_solid_color", 'rand_amt':5}
            ### Make stairs
            # Make right-hand staircase up to back corner
            step_height = 0
            start = 4
            for i in range(-1*start, self.a, -1):
                step_height += 3
                layout[(i,self.b-2)] = {'height':step_height, 'style':"style_shade_faces_solid_color", 'rand_amt':0}
            # Make left-hand staircase up to back corner
            step_height = 0
            for i in range(start-1, self.b-2):
                step_height += 3
                layout[(self.a+1,i)] = {'height':step_height, 'style':"style_shade_faces_solid_color", 'rand_amt':0}

        self.layout = layout

class VoxelArtwork:
    """Extrude voxels on the isometric grid.

    :param game -- the Game (for access to all the Game data)
    :param percentage:float -- percentage that each tile is covered by the voxel
    """
    def __init__(self, game, percentage:float=1.0):
        self.game = game
        self.N = self.game.grid.N
        self._percentage = percentage
        # TODO: Move this out to a level editor later
        # Make a layout of voxels in grid space
        # self.layout = self.make_random_layout()
        self.layout = self.make_voxels_from_tile_map()

    @property
    def percentage(self) -> float:
        return self._percentage
    @percentage.setter
    def percentage(self, value:float):
        self._percentage = value

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
                # grid_points = [[G[0]   + d,G[1]   + d],
                #                [G[0]+1 - d,G[1]   + d],
                #                [G[0]+1 - d,G[1]+1 - d],
                #                [G[0]   + d,G[1]+1 - d]]
                grid_points = [(G[0]  ,G[1]  ),
                               (G[0]+1,G[1]  ),
                               (G[0]+1,G[1]+1),
                               (G[0]  ,G[1]+1)]
                voxel_artwork.append([grid_points,height])
        return voxel_artwork

    def make_voxels_from_tile_map(self) -> dict:
        """Return a dict of voxels ready for rendering.

        Dict of voxels:
        key: same key as tilemap
        value: dict that describes the voxel
        """
        voxel_artwork = {}
        for G in self.game.tile_map.layout:
            # TEMPORARY: assume for now that every thing is a wall
            wall = self.game.tile_map.layout[G]
            height = wall['height']
            if wall['rand_amt'] > 0:
                height = random.choice(list(range(wall['height'],wall['height']+wall['rand_amt'])))
            grid_points = [(G[0]  ,G[1]  ),
                           (G[0]+1,G[1]  ),
                           (G[0]+1,G[1]+1),
                           (G[0]  ,G[1]+1)]
            voxel_artwork[G] = {'grid_points':grid_points, 'height':height, 'style':wall['style']}
        return voxel_artwork


    def old_make_voxels_from_tile_map(self) -> list:
        """Return a list of voxels ready for rendering.

        Old:
        Each item in the list is a Voxel, expressed as list [points:list, height:int].
        Height is assigned here: a nominal height is assigned in the tile map,
        but a small random change in height is added here.
        """

        voxel_artwork = []
        ### OLD
        # a = -1*int(self.N/2)
        # b = int(self.N/2)
        # wall1 = Wall(points=[(i,  a)   for i in range(a,b)], height=25, style="style_shade_faces_solid_color")  # Front left wall
        # wall2 = Wall(points=[(i,  b-1) for i in range(a,b)], height=65, style="style_shade_faces_solid_color")  # Back right wall
        # wall3 = Wall(points=[(a,  i)   for i in range(a,b)], height=65, style="style_shade_faces_solid_color")  # Back left wall
        # wall4 = Wall(points=[(b-1,i)   for i in range(a,b)], height=25, style="style_skeleton_frame")           # Front right wall
        # walls = [wall1, wall2, wall3, wall4]

        a = self.game.tile_map.a
        b = self.game.tile_map.b
        # walls = self.game.tile_map.walls
        # Decrement y values so that the draw order is correct for how I am
        # drawing voxels: I have to draw the ones "behind" first.
        for j in range(b,a-1,-1):
            for i in range(a,b):
                G = (i,j)
                # for wall in walls:
                #     if G in wall.points:
                        # height = random.choice(list(range(wall.height,wall.height+5)))
                        # grid_points = [(G[0]  ,G[1]  ),
                        #                (G[0]+1,G[1]  ),
                        #                (G[0]+1,G[1]+1),
                        #                (G[0]  ,G[1]+1)]
                        # voxel_artwork.append([grid_points,height,wall.style])
                        # break
                if G in self.game.tile_map.layout:
                    wall = self.game.tile_map.layout[G]
                    height = random.choice(list(range(wall['height'],wall['height']+5)))
                    grid_points = [(G[0]  ,G[1]  ),
                                   (G[0]+1,G[1]  ),
                                   (G[0]+1,G[1]+1),
                                   (G[0]  ,G[1]+1)]
                    voxel_artwork.append([grid_points,height,wall['style']])
        return voxel_artwork

    def adjust_voxel_size(self) -> dict:
        """Scale size of each voxel by some percentage."""
        adjusted_voxel_artwork = {}
        # Calculate how much to shrink voxels
        p = 1-self.percentage
        d = p/2
        # Convert each voxel to pixel coordinates and render
        # TODO: rename self.layout to self.voxel_dict or something more descriptive
        for G in self.layout:
            Gs = self.layout[G]['grid_points']
            adjusted_grid_points = [
                    (Gs[0][0] + d, Gs[0][1] + d),
                    (Gs[1][0] - d, Gs[1][1] + d),
                    (Gs[2][0] - d, Gs[2][1] - d),
                    (Gs[3][0] + d, Gs[3][1] - d)
                    ]
            # Copy height and style
            height = self.layout[G]['height']
            style = self.layout[G]['style']
            # Apply self.percentage and keep the voxel centered on the tile
            adjusted_voxel_artwork[G] = {'grid_points':adjusted_grid_points,'height':height,'style':style}
        return adjusted_voxel_artwork

    def old_adjust_voxel_size(self) -> list:
        """Scale size of each voxel by some percentage."""
        adjusted_voxel_artwork = []
        # Calculate how much to shrink voxels
        p = 1-self.percentage
        d = p/2
        # Convert each voxel to pixel coordinates and render
        for voxel in self.layout:
            Gs = voxel[0]
            height = voxel[1]
            style = voxel[2]
            adjusted_grid_points = [
                    (Gs[0][0] + d, Gs[0][1] + d),
                    (Gs[1][0] - d, Gs[1][1] + d),
                    (Gs[2][0] - d, Gs[2][1] - d),
                    (Gs[3][0] + d, Gs[3][1] - d)
                    ]
            # Apply self.percentage and keep the voxel centered on the tile
            adjusted_voxel_artwork.append([adjusted_grid_points,height,style])
        return adjusted_voxel_artwork

    def render(self, surf) -> None:
        """Render voxels, player, and mouse."""
        voxels = self.adjust_voxel_size()
        player = self.game.player
        mouse = self.game.grid.xfm_pg(pygame.mouse.get_pos())

        ### voxels[G] = {'grid_points':grid_points, 'height':height, 'style':wall['style']}
        # Make a back-to-front draw order
        a = self.game.tile_map.a # -25
        b = self.game.tile_map.b # +25
        grid_list = [] # Walk grid coordinates in the order listed here
        for j in range(b,a-1,-1):
            for i in range(a,b):
                G = (i,j)
                grid_list.append(G)
        # logger.debug(grid_list)
        ### [(-25,  25), (-24,  25), ... (0,  25), ... (24,  25),
        ###  (-25,  24), (-24,  24), ... (0,  24), ... (24,  24),
        ###  ...
        ###  (-25, -25), (-24, -25), ... (0, -25), ... (24, -25)]

        # TODO: come back to this idea -- maybe I run this for everything to store a draw order with every voxel and object.
        # Figure out when to draw the player
        # player_draw_index = 0
        # for i,G in enumerate(grid_list):
        #     if G in voxels:
        #         if (player.pos[0] >= G[0]) and (player.pos[1] <= G[1]):
        #             # Player is in front of this voxel; update draw order
        #             player_draw_index = i + 1

        # Figure out when to draw the player and mouse
        player_draw_index = 0; mouse_draw_index = 0; voxel_index=0
        for G in grid_list:
            if G in voxels:
                voxel_index += 1
                if (player.pos[0] >= G[0]) and (player.pos[1] <= G[1]):
                    # Player is in front of this voxel; update draw order
                    player_draw_index = voxel_index + 1
                if (mouse[0] >= G[0]) and (mouse[1] <= G[1]):
                    mouse_draw_index = voxel_index + 1

        # for i,G in enumerate(grid_list):
        voxel_index = 0 # draw_index
        for G in grid_list:
            if G in voxels:
                voxel_index += 1
                ### Draw voxel
                # Convert the base quad grid points to pixel points
                Ps = [self.game.grid.xfm_gp(grid_point) for grid_point in voxels[G]['grid_points']]
                # Describe the three visible surfaces of the voxel as quads
                ### T: Top, L: Left, R: Right
                height = voxels[G]['height']
                voxel_Ts = [(P[0],P[1] - height*self.game.grid.scale) for P in Ps]
                voxel_Ls = [Ps[0], Ps[1], voxel_Ts[1], voxel_Ts[0]]
                voxel_Rs = [Ps[1], Ps[2], voxel_Ts[2], voxel_Ts[1]]
                style = voxels[G]['style']
                match style:
                    case "style_shade_faces_solid_color":
                        # Render the three visible quads
                        ### polygon(surface, color, points) -> Rect
                        pygame.draw.polygon(surf, self.game.colors['color_voxel_top'], voxel_Ts)
                        pygame.draw.polygon(surf, self.game.colors['color_voxel_left'], voxel_Ls)
                        pygame.draw.polygon(surf, self.game.colors['color_voxel_right'], voxel_Rs)
                    case "style_skeleton_frame":
                        ### polygon(surface, color, points, width=0) -> Rect
                        pygame.draw.polygon(surf, self.game.colors['color_voxel_top'], voxel_Ts, width=1)
                        pygame.draw.polygon(surf, self.game.colors['color_voxel_left'], voxel_Ls, width=1)
                        pygame.draw.polygon(surf, self.game.colors['color_voxel_right'], voxel_Rs, width=1)
                    case _:
                        pass
                # Check if mouse is at this voxel
                if G == mouse:
                    # Draw mouse location highlighting the top of the voxel
                    points_zh = [(P[0], P[1] - height*self.game.grid.scale) for P in Ps]
                    # Draw a yellow highlight above the voxel
                    pygame.draw.polygon(surf, Color(200,200,100), points_zh)
            # TODO: do not draw green highlight if drawing a yellow highlight
            # Check draw order for mouse
            if voxel_index == mouse_draw_index:
                # Draw the mouse green highlight on the grid
                self.game.render_grid_tile_highlighted_at_mouse()
            # Check draw order for player
            if voxel_index == player_draw_index:
                # Draw player
                player.render(surf)
        # DEBUG
        ### DebugHud.add_text(debug_text:str)
        if self.game.debug_hud:
            self.game.debug_hud.add_text(f"player_draw_index: {player_draw_index}")
            self.game.debug_hud.add_text(f"len(voxels): {len(voxels)}")
            self.game.debug_hud.add_text(
                    f"player.pos: ({player.pos[0]:.1f},{player.pos[1]:.1f},z={player.z:.1f})")

        # If mouse is in front of all voxels, player has not been drawn yet!
        if mouse_draw_index >= len(voxels):
            self.game.render_grid_tile_highlighted_at_mouse()
        # If player is in front of all voxels, player has not been drawn yet!
        if player_draw_index >= len(voxels):
            # Draw the player now
            player.render(surf)

    def old_render(self, surf) -> None:
        """Render voxels and player.

        Figure out which voxels the player is "in front" / "behind". Determine
        correct draw order for the player in relation to the list of voxels.

        Implementation
        --------------
        "In front" and "behind" is handled by draw order. I draw everything
        and let draw order do the work for me. This is wasteful. But this is
        just a prototype: as long as frame rate does not get in the way of
        testing, I do not care how performant the code is.

        "In front" and "behind" is simply determined by grid coordinate (x,y)
        value. Consider player, p, and voxel, v. Visualize the grid as a
        top-down view using conventional x,y axes: +x is right, +y is up.
        Player p is in front of voxel v if px >= vx and py <= vy. Perform this
        test to determine the player index in the list of voxels.

        Iterate over all voxels and draw each one. When voxel index matches
        player index, draw draw player.
        """
        # TEMPORARY: Adjust size of voxels based on percentage that it fills its tile
        # TODO: give each voxel its own percentage
        voxels = self.adjust_voxel_size()

        # Figure out when to draw player in list of voxels for correct draw order
        player = self.game.player
        player_voxel_index = 0                          # 0 : draw first
        # TODO: iterate over this backwards and break after first hit
        for i,voxel in enumerate(voxels):
            grid_points = voxel[0]
            lower_left = grid_points[0]                 # 0 : Lower left corner
            if (player.pos[0] >= lower_left[0]) and (player.pos[1] <= lower_left[1]):
                # Player is in front of this voxel; update draw order
                player_voxel_index = i + 1

        # DEBUG
        ### DebugHud.add_text(debug_text:str)
        if self.game.debug_hud:
            self.game.debug_hud.add_text(
                    f"player_voxel_index: i={player_voxel_index}, "
                    f"player.pos: ({player.pos[0]:.1f},{player.pos[1]:.1f},z={player.z:.1f})")

        # Convert each voxel to pixel coordinates and render
        for i,voxel in enumerate(voxels):
            # Draw player
            if  i == player_voxel_index:
                player.render(surf)
            # Draw voxels
            grid_points = voxel[0]
            height = voxel[1]
            style = voxel[2]
            Gs = grid_points
            # What is the index of the inner wall voxel at (10,3)?
            if Gs[0] == (9.0,3.0):
                # DEBUG
                ### DebugHud.add_text(debug_text:str)
                if self.game.debug_hud:
                    self.game.debug_hud.add_text(
                            f"inner wall voxel index: i={i}, "
                            f"voxel grid_points: {grid_points}")
            # Convert to pixel coordinates
            Ps = [self.game.grid.xfm_gp(G) for G in grid_points]
            # Describe the three visible surfaces of the voxel as quads
            ### T: Top, L: Left, R: Right
            voxel_Ts = [(P[0],P[1] - height*self.game.grid.scale) for P in Ps]
            voxel_Ls = [Ps[0], Ps[1], voxel_Ts[1], voxel_Ts[0]]
            voxel_Rs = [Ps[1], Ps[2], voxel_Ts[2], voxel_Ts[1]]
            match style:
                case "style_shade_faces_solid_color":
                    # Render the three visible quads
                    ### polygon(surface, color, points) -> Rect
                    pygame.draw.polygon(surf, self.game.colors['color_voxel_top'], voxel_Ts)
                    pygame.draw.polygon(surf, self.game.colors['color_voxel_left'], voxel_Ls)
                    pygame.draw.polygon(surf, self.game.colors['color_voxel_right'], voxel_Rs)
                    # DEBUG
                    if Gs[0] == (9.0,3.0):
                        pygame.draw.polygon(surf, Color(255,255,0), voxel_Ts)
                case "style_skeleton_frame":
                    ### polygon(surface, color, points, width=0) -> Rect
                    pygame.draw.polygon(surf, self.game.colors['color_voxel_top'], voxel_Ts, width=1)
                    pygame.draw.polygon(surf, self.game.colors['color_voxel_left'], voxel_Ls, width=1)
                    pygame.draw.polygon(surf, self.game.colors['color_voxel_right'], voxel_Rs, width=1)
                case _:
                    pass
        # If player is in front of all voxels, player has not been drawn yet!
        if player_voxel_index == len(voxels):
            # Draw the player now
            player.render(surf)

class Universe:
    """Recognize spells and then executes them."""
    pass


class RomanizedChars:
    """Set up game with Romanized Characters.

    Loads image of romanized character spritesheet into Game surfs['surf_romanized_chars'].

    Attributes
    ----------
    name:str -- name of spritesheet ("romanized_chars")
    scale:float -- scale the size of the romanized chars by this amount (e.g., 0.5)
    size:tuple -- (w,h) of a romanized char (every spritesheet frame is the same size)
    letters:dict -- Dict key is letter name, value is index into the spritesheet,
                    e.g., {'f': 0, 'k': 1, 'u': 2, 't': 3, ...}

                    Use event.unicode to find the index into the spritesheet:

                    if event.unicode in self.romanized_chars.letters:
                        index = self.romanized_chars.letters[event.unicode]
    """
    def __init__(self, game):
        self.game = game
        # Display romanized chars by pulling Rects from an Aseprite spritesheet
        romanized_chars_spritesheet_path = Path('../spells/data/images/romanized_chars.png')
        # Load a pygame Surface with the spritesheet .png
        # self.game.surfs['surf_romanized_chars'] = load_image(romanized_chars_spritesheet_path).convert()
        full_size_surf = load_image(romanized_chars_spritesheet_path).convert()
        self.scale = 20/64
        size = (self.scale*full_size_surf.get_width(), self.scale*full_size_surf.get_height())
        self.game.surfs['surf_romanized_chars'] = pygame.transform.smoothscale(full_size_surf, size)
        self.name = romanized_chars_spritesheet_path.stem # name: "romanized_chars"

        # Extract JSON data fromm Aseprite JSON export
        romanized_chars_json_path = romanized_chars_spritesheet_path.with_suffix('.json')
        with open(romanized_chars_json_path) as fp:
            romanized_chars_data = json.load(fp)

        # Extract w,h from JSON data
        layer_name = f'{self.name}'                     # Layer name in Aseprite JSON
        a_romanized_char = romanized_chars_data['frames'][f'{layer_name} 0.aseprite']['frame']
        # self.size = (a_romanized_char['w'], a_romanized_char['h'])
        # logger.debug(f"{self.size}") # (48, 64)
        self.size = (self.scale*a_romanized_char['w'], self.scale*a_romanized_char['h'])

        # Extract letter locations from JSON data
        self.letters = {}                               # Dict of romanized chars
        for letter_tag in romanized_chars_data['meta']['frameTags']:
            # Create a dictionary: key = letter name, value = letter index
            ### {'f': 0, 'k': 1, 'u': 2, 't': 3, ...}
            self.letters[letter_tag['name']]=letter_tag['from']
        logger.debug(f"{self.letters}")

class Game:
    def __init__(self):
        pygame.init()                                   # Init pygame -- quit in shutdown
        pygame.font.init()                              # Initialize the font module

        os.environ["PYGAME_BLEND_ALPHA_SDL2"] = "1"     # Use SDL2 alpha blending
        # os.environ["SDL_VIDEO_WINDOW_POS"] = "1000,0"   # Position window in upper right

        self.os_window = OsWindow((120*16, 120*9), is_fullscreen=True) # Track OS Window size
        logger.debug(f"Window size: {self.os_window.size[0]} x {self.os_window.size[1]}")

        self.surfs = define_surfaces(self.os_window)    # Dict of Pygame Surfaces (including pygame.display)
        pygame.display.set_caption("Isometric grid test")
        self.colors = define_colors()                   # Dict of Pygame Colors
        self.actions = define_actions()                 # Dict of player actions (what to do when Space is pressed)
        self.moves = define_moves()                     # Dict of player movements
        self.keys = define_held_keys()                  # Dict of which keyboard inputs are being held down
        self.settings = define_settings()               # Dict of settings
        pygame.mouse.set_visible(False)                 # Hide the OS mouse icon

        # Game Data
        self.grid = Grid(self, N=50)
        self.tile_map = TileMap(N=self.grid.N)
        self.voxel_artwork = VoxelArtwork(self)
        self.gravity = 0.5
        self.max_fall_speed = 15.0
        self.player = Player(self)
        self.romanized_chars = RomanizedChars(self)
        self.mouses = {}

        # FPS
        self.clock = pygame.time.Clock()

    def run(self):
        while True: self.game_loop()

    def game_loop(self):
        # Create the debug HUD
        if self.settings['setting_debug']:
            self.debug_hud = DebugHud(self)
        else:
            self.debug_hud = None

        # Update things affected by gravity
        self.update_gravity_effects()

        # Handle keyboard and mouse
        # Zoom by scrolling the mouse wheel
        # Pan by pressing the mouse wheel or left-clicking
        self.handle_ui_events()
        if self.grid.is_panning:
            self.grid.pan(pygame.mouse.get_pos())

        self.update_held_keys_effects()
        self.update_player_actions()
        self.update_player_movement()

        # Clear screen
        ### fill(color, rect=None, special_flags=0) -> Rect
        self.surfs['surf_game_art'].fill(self.colors['color_game_art_bgnd'])

        # TEMPORARY: Draw a floor as a single giant square
        a = self.tile_map.a
        b = self.tile_map.b
        points = [self.grid.xfm_gp(G) for G in [(a,a), (b,a), (b,b), (a,b)]]
        ### polygon(surface, color, points) -> Rect
        pygame.draw.polygon(self.surfs['surf_game_art'], self.colors['color_floor_solid'], points)

        # Draw grid
        if self.settings['setting_debug']:
            self.grid.draw(self.surfs['surf_game_art'])

        # TODO: draw floor tiles

        # Display mouse coordinates in game grid coordinate system
        mpos_p = pygame.mouse.get_pos()                   # Mouse in pixel coord sys
        mpos_g = self.grid.xfm_pg(mpos_p)
        if self.debug_hud:
            self.debug_hud.add_text(f"Mouse (grid): {mpos_g}")

        # Draw the layout of voxels and player
        self.voxel_artwork.render(self.surfs['surf_game_art'])

        # Figure out which voxel is below the player
        self.player.update_voxel()
        if self.debug_hud:
            self.debug_hud.add_text(f"self.player.voxel: {self.player.voxel}")

        # self.render_mouse_location_as_white_circle()
        # Use the power of xfm_gp()
        # self.render_grid_tile_highlighted_at_mouse()
        self.update_mouse_height()
        if self.debug_hud:
            self.debug_hud.add_text(f"mouse_height: {self.mouses['mouse_height']}")

        if self.debug_hud:
            self.debug_hud.add_text(f"Voxel %: {int(100*self.voxel_artwork.percentage)}%")

        # Display transform matrix element values a,b,c,d,e,f
        if self.debug_hud:
            a,b,c,d = self.grid.scaled()
            e,f = (self.grid.e, self.grid.f)
            self.debug_hud.add_text(f"a: {a:0.1f} | b: {b:0.1f} | c: {c:0.1f} | d: {d:0.1f} | e: {e:0.1f} | f: {f:0.1f}")

        ### TEMPORARY: spell casting
        # Display typing text while casting
        if self.player.is_casting:
            # Display romanized chars above player if spell casting
            self.player.render_romanized_chars(self.surfs['surf_game_art'])
            # Display keystrokes at bottom of screen in debug font
            self.render_debug_keystrokes(self.surfs['surf_game_art'])


        # Copy game art to OS window
        ### blit(source, dest, area=None, special_flags=0) -> Rect
        self.surfs['surf_os_window'].blit(self.surfs['surf_game_art'], (0,0))

        ### TEMPORARY: spell casting
        # DEBUG: What spell is cast?
        if self.debug_hud:
            if self.player.spell != "":
                self.debug_hud.add_text(f"Cast: {self.player.spell}")

        # Display Debug HUD overlay
        if self.debug_hud:
            self.debug_hud.render(self.colors['color_debug_hud'])

        # Display HELP below DEBUG
        if self.settings['setting_show_help']:
            self.help_hud = HelpHud(self)
            self.help_hud.add_text("View:")
            self.help_hud.add_text("  - Mouse wheel: zoom")
            self.help_hud.add_text("  - 'e,f,E,F': pan camera")
            self.help_hud.add_text("  - 'a,b,c,d,A,B,C,D': manipulate Xfm")
            self.help_hud.add_text("  - 'r': reset view")
            self.help_hud.add_text("Player:")
            self.help_hud.add_text("  - 'Left-click': place player")
            self.help_hud.add_text("  - 'Space': levitate player")
            self.help_hud.add_text("Movement:")
            self.help_hud.add_text("  - 'j,k': player down/up (Shift: nudge)")
            self.help_hud.add_text("  - 'h,l': player left/right (Shift: nudge)")
            self.help_hud.add_text("SPELLCASTING")
            if self.player.is_casting:
                self.help_hud.add_text("  - (Type stuff)")
                self.help_hud.add_text("  - 'Backspace': unspeak last?")
                self.help_hud.add_text("  - 'Esc': cancel casting")
                self.help_hud.add_text("  - 'Enter': cast")
            else:
                self.help_hud.add_text("  - ':': start casting")
            if self.debug_hud:
                # Bump HelpHud down below the DebugHUD
                self.help_hud.text.pos = (0,len(self.debug_hud.text.text_lines)*self.debug_hud.text.font.get_linesize())
            self.help_hud.render(self.colors['color_help_hud'])

        # Draw to the OS window
        pygame.display.update()

        ### clock.tick(framerate=0) -> milliseconds
        self.clock.tick(60)

    def update_gravity_effects(self) -> None:
        # Account for gravity
        self.player.dz = min(self.max_fall_speed, self.player.dz+self.gravity) # acceleration updates velocity
        self.player.z += self.player.dz                 # velocity updates position

        # Stop falling if player is standing on something
        floor_height = 0
        if self.player.voxel != None:
            floor_height = -1*self.player.voxel['height']*self.grid.scale
            if self.debug_hud: self.debug_hud.add_text(f"floor_height: {floor_height}")
        if self.player.z > floor_height:
            # z > 0 means player is BELOW the floor
            self.player.z = floor_height                # reset position
            self.player.dz = 0                          # reset velocity


    def handle_ui_events(self) -> None:
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
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
                        case 1:
                            logger.debug("Left-click")
                            if kmod & pygame.KMOD_SHIFT:
                                # Let shift_left-click be my panning
                                # because I cannot do right-click-and-drag on the laptop trackpad
                                self.handle_mousebuttondown_middleclick()
                            else:
                                # Place the player
                                self.player.pos = self.grid.xfm_pg(event.pos)
                                self.player.z = -1*self.grid.scale*self.mouses['mouse_height']
                        case 2:
                            logger.debug("Middle-click")
                            self.handle_mousebuttondown_middleclick()
                        case 3: logger.debug("Right-click")
                        case 4: logger.debug("Mousewheel y=+1")
                        case 5: logger.debug("Mousewheel y=-1")
                        case 6: logger.debug("Logitech G602 Thumb button 6")
                        case 7: logger.debug("Logitech G602 Thumb button 7")
                        case _: logger.debug(event)
                case pygame.MOUSEBUTTONUP:
                    match event.button:
                        case 1:
                            if kmod & pygame.KMOD_SHIFT:
                                logger.debug("Shift+Left mouse button released")
                                self.handle_mousebuttonup_middleclick()
                        case 2:
                            logger.debug("Middle mouse button released")
                            self.handle_mousebuttonup_middleclick()
                        case _: logger.debug(event)
                # Log any other events
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")

    def handle_mousebuttondown_middleclick(self) -> None:
        self.grid.pan_ref = pygame.mouse.get_pos()
        self.grid.is_panning = True

    def handle_mousebuttonup_middleclick(self) -> None:
        self.grid.pan_ref = (None, None)
        self.grid.pan_origin = (self.grid.e, self.grid.f)
        self.grid.is_panning = False

    def handle_keyup(self, event) -> None:
        kmod = pygame.key.get_mods()
        # Key behavior is modal: keyup has no significance while casting
        if not self.player.is_casting:
            match event.key:
                case pygame.K_LSHIFT:
                    self.keys['key_Shift_Space'] = False
                    # self.keys['key_A'] = False
                    # self.keys['key_B'] = False
                    # self.keys['key_C'] = False
                    # self.keys['key_D'] = False
                    self.keys['key_E'] = False
                    self.keys['key_F'] = False
                case pygame.K_SPACE:
                    self.keys['key_Space'] = False
                    self.keys['key_Shift_Space'] = False
                # case pygame.K_a:
                #     self.keys['key_A'] = False
                #     self.keys['key_a'] = False
                # case pygame.K_b:
                #     self.keys['key_B'] = False
                #     self.keys['key_b'] = False
                # case pygame.K_c:
                #     self.keys['key_C'] = False
                #     self.keys['key_c'] = False
                # case pygame.K_d:
                #     self.keys['key_D'] = False
                #     self.keys['key_d'] = False
                case pygame.K_e:
                    self.keys['key_E'] = False
                    self.keys['key_e'] = False
                case pygame.K_f:
                    self.keys['key_F'] = False
                    self.keys['key_f'] = False
                # Free player movement
                case pygame.K_s: # Move Down
                    self.keys['key_s'] = False
                case pygame.K_w: # Move Up
                    self.keys['key_w'] = False
                case pygame.K_a: # Move Left
                    self.keys['key_a'] = False
                case pygame.K_d: # Move Right
                    self.keys['key_d'] = False
                case _:
                    pass

    def handle_keydown(self, event) -> None:
        # Key behavior is modal
        if self.player.is_casting:
            self.handle_keydown_casting(event)
        else:
            self.handle_keydown_held_keys(event)
            self.handle_keydown_single_shot(event)

    def handle_keydown_casting(self, event) -> None:
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
        match event.key:
            case pygame.K_RETURN:
                # Cast this spell
                self.player.spell = self.player.keystrokes.lstrip(":")
                self.player.keystrokes = ""
                self.player.is_casting = False
            case pygame.K_ESCAPE:
                # Abort casting
                self.player.keystrokes = ""
                self.player.is_casting = False
            case pygame.K_BACKSPACE:
                self.player.keystrokes = self.player.keystrokes[0:-1]
            case pygame.K_a:
                if kmod & pygame.KMOD_SHIFT:
                    self.player.keystrokes += 'á'
                else:
                    self.player.keystrokes += event.unicode
            case pygame.K_e:
                if kmod & pygame.KMOD_SHIFT:
                    self.player.keystrokes += 'é'
                else:
                    self.player.keystrokes += event.unicode
            case pygame.K_c:
                if kmod & pygame.KMOD_SHIFT:
                    self.player.keystrokes += 'ċ'
                else:
                    self.player.keystrokes += event.unicode
            case pygame.K_l:
                if kmod & pygame.KMOD_SHIFT:
                    self.player.keystrokes += 'L' # 'ļ' json.decoder.JSONDecodeError: Invalid control character
                elif kmod & pygame.KMOD_ALT:
                    self.player.keystrokes += 'T' # 'ł' json.decoder.JSONDecodeError: Invalid control character
                else:
                    self.player.keystrokes += event.unicode
            case _:
                self.player.keystrokes += event.unicode            # Append key-stroke
                logger.debug(f"self.player.keystrokes: {self.player.keystrokes}")

    def handle_keydown_single_shot(self, event) -> None:
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
        # Handle single-shot key presses
        match event.key:
            case pygame.K_q: sys.exit()                 # q - Quit
            case pygame.K_F11:
                self.os_window.toggle_fullscreen() # F11 - toggle fullscreen
                self.surfs = define_surfaces(self.os_window)
                self.grid.reset()
            case pygame.K_SEMICOLON:
                if kmod & pygame.KMOD_SHIFT:
                    self.player.is_casting = True
            case pygame.K_F1:
                self.settings['setting_show_help'] = not self.settings['setting_show_help']
            case pygame.K_F2:                           # F2 - Toggle Debug
                self.settings['setting_debug'] = not self.settings['setting_debug']
            # TEMPORARY adjust percentage that voxels cover tiles
            case pygame.K_UP:
                self.voxel_artwork.percentage = min(1.0, self.voxel_artwork.percentage + 0.1)
            case pygame.K_DOWN:
                self.voxel_artwork.percentage = max(0.0, self.voxel_artwork.percentage - 0.1)
            case pygame.K_r:
                # Reset view back to initial view after changing Xfm matrix values (a,b,c,d,e,f,zoom)
                self.grid.reset()
            case pygame.K_z:
                if kmod & pygame.KMOD_SHIFT:
                    self.grid.zoom_in()
                else:
                    self.grid.zoom_out()
            # Discrete player movement
            # TODO: Animate discrete tile movement
            # TODO: discrete tile movement continues until player is perfectly on a tile
            case pygame.K_j:
                self.moves['move_down_to_tile'] = True
            case pygame.K_k:
                pos = self.player.pos
                self.player.pos = (pos[0],pos[1] + 1)
                # logger.debug("Move Up")
            case pygame.K_h:
                pos = self.player.pos
                self.player.pos = (pos[0] - 1 , pos[1])
                # logger.debug("Move Left")
            case pygame.K_l:
                pos = self.player.pos
                self.player.pos = (pos[0] + 1 , pos[1])
                # logger.debug("Move Right")
            # TEMPORARY: Print name of keys that have no unicode representation.
            case pygame.K_RETURN: logger.debug("Return")
            case pygame.K_ESCAPE: logger.debug("Esc")
            case pygame.K_BACKSPACE: logger.debug("Backspace")
            case pygame.K_DELETE: logger.debug("Delete")
            case pygame.K_F3: logger.debug("F3")
            case pygame.K_F4: logger.debug("F4")
            case pygame.K_F5: logger.debug("F5")
            case pygame.K_F6: logger.debug("F6")
            case pygame.K_F7: logger.debug("F7")
            case pygame.K_F8: logger.debug("F8")
            case pygame.K_F9: logger.debug("F9")
            case pygame.K_F10: logger.debug("F10")
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

    def handle_keydown_held_keys(self, event) -> None:
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
        match event.key:
            case pygame.K_SPACE:
                if kmod & pygame.KMOD_SHIFT:
                    # TEMPORARY randomize voxel artwork
                    self.keys['key_Shift_Space'] = True
                else:
                    # TEMPORARY levitate player
                    self.keys['key_Space'] = True
            # TEMPORARY manipulate the xfm matrix
            # case pygame.K_a:
            #     if kmod & pygame.KMOD_SHIFT:
            #         self.keys['key_A'] = True
            #     else:
            #         self.keys['key_a'] = True
            # case pygame.K_b:
            #     if kmod & pygame.KMOD_SHIFT:
            #         self.keys['key_B'] = True
            #     else:
            #         self.keys['key_b'] = True
            # case pygame.K_c:
            #     if kmod & pygame.KMOD_SHIFT:
            #         self.keys['key_C'] = True
            #     else:
            #         self.keys['key_c'] = True
            # case pygame.K_d:
            #     if kmod & pygame.KMOD_SHIFT:
            #         self.keys['key_D'] = True
            #     else:
            #         self.keys['key_d'] = True
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
            # Free player movement
            case pygame.K_s: # Move Down
                if kmod & pygame.KMOD_SHIFT:
                    # 'Shift+J' nudges player
                    pos = self.player.pos
                    self.player.pos = (pos[0],                      pos[1] - self.player.speed_walk)
                else:
                    self.keys['key_s'] = True
            case pygame.K_w: # Move Up
                if kmod & pygame.KMOD_SHIFT:
                    # 'Shift+K' nudges player
                    pos = self.player.pos
                    self.player.pos = (pos[0],                      pos[1] + self.player.speed_walk)
                else:
                    self.keys['key_w'] = True
            case pygame.K_a: # Move Left
                if kmod & pygame.KMOD_SHIFT:
                    # 'Shift+H' nudges player
                    pos = self.player.pos
                    self.player.pos = (pos[0] - self.player.speed_walk,  pos[1])
                else:
                    self.keys['key_a'] = True
            case pygame.K_d: # Move Right
                if kmod & pygame.KMOD_SHIFT:
                    # 'Shift+L' nudges player
                    pos = self.player.pos
                    self.player.pos = (pos[0] + self.player.speed_walk,  pos[1])
                else:
                    self.keys['key_d'] = True
            case _:
                pass


    def update_held_keys_effects(self) -> None:
        self.update_held_keys_effects_grid_xfm()
        self.update_held_keys_effects_player_movement()

        # Pick what action to do when Space is held
        self.actions['action_levitate'] = self.keys['key_Space']

        # Randomize voxel artwork if Shift+Space is held
        if self.keys['key_Shift_Space']:
            # self.voxel_artwork.layout = self.voxel_artwork.make_random_layout()
            self.voxel_artwork.layout = self.voxel_artwork.make_voxels_from_tile_map()

    def update_held_keys_effects_grid_xfm(self) -> None:
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
        # Update transform based on key presses
        if self.keys['key_A']: self.grid.a += 1
        if self.keys['key_B']: self.grid.b += 1
        if self.keys['key_C']: self.grid.c += 1
        if self.keys['key_D']: self.grid.d += 1
        # if self.keys['key_a']: self.grid.a -= 1
        if self.keys['key_b']: self.grid.b -= 1
        if self.keys['key_c']: self.grid.c -= 1
        # if self.keys['key_d']: self.grid.d -= 1
        if self.keys['key_E']: self.grid.e += 1
        if self.keys['key_e']: self.grid.e -= 1
        if self.keys['key_F']: self.grid.f += 1
        if self.keys['key_f']: self.grid.f -= 1

    def update_held_keys_effects_player_movement(self) -> None:
        # Free player movement
        self.moves['move_down']  = self.keys['key_s']
        self.moves['move_up']    = self.keys['key_w']
        self.moves['move_left']  = self.keys['key_a']
        self.moves['move_right'] = self.keys['key_d']

    # TODO: move to Player
    def update_player_actions(self) -> None:
        # Levitate player if Space is held
        if self.actions['action_levitate']:
            self.player.dz = 0                          # reset velocity (turn off gravity)
            self.player.z -= self.player.speed_rise     # levitate

    # TODO: move to Player
    def update_player_movement(self) -> None:
        # DEBUG moves
        if self.debug_hud:
            self.debug_hud.add_text(f"self.moves: {self.moves}")

        if self.moves['move_down'] or self.moves['move_up'] or self.moves['move_left'] or self.moves['move_right']:
            self.player.moving = True
        else:
            self.player.moving = False
        if self.moves['move_down_to_tile']:
            pos = self.player.pos
            self.player.pos = (pos[0],pos[1] - 1)
            # logger.debug("Move Down")
            self.moves['move_down_to_tile'] = False
        if self.moves['move_down']:
            pos = self.player.pos
            speed = self.player.speed_walk
            # Scale walking speed if moving DOWN+LEFT or DOWN+RIGHT
            if self.moves['move_left'] or self.moves['move_right']:
                speed *= 0.7
            # Set new position
            self.player.pos = (pos[0],                      pos[1] - speed)
            # Collision detection
            neighbor_x = int(self.player.pos[0])
            # Going down? Look 1 tile "below" player
            # To look "below", comparison depends on whether player y is + or -
            if self.player.pos[1] < 0:
                # Example: player_y = -10.8, 1 tile below y=-11
                neighbor_y = int(self.player.pos[1]) - 1
            else:
                # Example: player_y = +10.8, 1 tile below y=+10
                neighbor_y = int(self.player.pos[1])
            if (neighbor_x,neighbor_y) in self.tile_map.layout:
                # There is a tile there.
                # Now check if the top of this tile is too high for the player to get onto
                G = (neighbor_x, neighbor_y)
                tile_height = self.voxel_artwork.layout[G]['height']
                too_high = (self.player.z  - self.player.zclimbmax*self.grid.scale) > -1*tile_height*self.grid.scale
                # TODO: make "too_high" a little higher than same height
                if too_high:
                    # Block the player from moving here
                    self.player.pos = (pos[0], neighbor_y+1)

        if self.moves['move_up']:
            # GO UP
            pos = self.player.pos
            speed = self.player.speed_walk
            # Scale walking speed if moving UP+LEFT or UP+RIGHT
            if self.moves['move_left'] or self.moves['move_right']:
                speed *= 0.7
            self.player.pos = (pos[0],                      pos[1] + speed)
            # Collision detection
            neighbor_x = int(self.player.pos[0])
            # Going up? Look 1 tile "above" player
            if self.player.pos[1] < 0:
                # Example: player_y = -10.8, 1 tile above y=-10
                neighbor_y = int(self.player.pos[1])
            else:
                # Example: player_y = +10.8, 1 tile above y=+11
                neighbor_y = int(self.player.pos[1]) + 1
            # for wall in self.tile_map.walls:
            #     if (neighbor_x,neighbor_y) in wall.points:
            #         self.player.pos = (pos[0], neighbor_y-1)
            if (neighbor_x,neighbor_y) in self.tile_map.layout:
                # There is a tile there.
                # Now check if the top of this tile is too high for the player to get onto
                G = (neighbor_x, neighbor_y)
                tile_height = self.voxel_artwork.layout[G]['height']
                too_high = (self.player.z  - self.player.zclimbmax*self.grid.scale) > -1*tile_height*self.grid.scale
                # TODO: make "too_high" a little higher than same height
                if too_high:
                    # Block the player from moving here
                    self.player.pos = (pos[0], neighbor_y-1)

        if self.moves['move_left']:
            pos = self.player.pos
            speed = self.player.speed_walk
            # Scale walking speed if moving LEFT+UP or LEFT+DOWN
            if self.moves['move_up'] or self.moves['move_down']:
                speed *= 0.7
            self.player.pos = (pos[0] - speed,  pos[1])
            # Collision detection
            neighbor_y = int(self.player.pos[1])
            if self.player.pos[0] < 0:
                # Example: Player_x = -10.8, 1 tile left x=-11
                neighbor_x = int(self.player.pos[0] - 1)
            else:
                # Example player_x = +10.8, 1 tile left x=+10
                neighbor_x = int(self.player.pos[0])
            # for wall in self.tile_map.walls:
            #     if (neighbor_x,neighbor_y) in wall.points:
            #         self.player.pos = (neighbor_x+1, pos[1])
            if (neighbor_x,neighbor_y) in self.tile_map.layout:
                # There is a tile there.
                # Now check if the top of this tile is too high for the player to get onto
                G = (neighbor_x, neighbor_y)
                tile_height = self.voxel_artwork.layout[G]['height']
                too_high = (self.player.z  - self.player.zclimbmax*self.grid.scale) > -1*tile_height*self.grid.scale
                # TODO: make "too_high" a little higher than same height
                if too_high:
                    # Block the player from moving here
                    self.player.pos = (neighbor_x+1, pos[1])

        if self.moves['move_right']:
            pos = self.player.pos
            speed = self.player.speed_walk
            # Scale walking speed if moving RIGHT+UP or RIGHT+DOWN
            if self.moves['move_up'] or self.moves['move_down']:
                speed *= 0.7
            self.player.pos = (pos[0] + speed,  pos[1])
            # Collision detection
            neighbor_y = int(self.player.pos[1])
            if self.player.pos[0] < 0:
                # Example: Player_x = -10.8, 1 tile right x=-10
                neighbor_x = int(self.player.pos[0])
            else:
                # Example player_x = +10.8, 1 tile right x=+11
                neighbor_x = int(self.player.pos[0] + 1)
            # for wall in self.tile_map.walls:
            #     if (neighbor_x,neighbor_y) in wall.points:
            #         self.player.pos = (neighbor_x-1, pos[1])
            if (neighbor_x,neighbor_y) in self.tile_map.layout:
                # There is a tile there.
                # Now check if the top of this tile is too high for the player to get onto
                G = (neighbor_x, neighbor_y)
                tile_height = self.voxel_artwork.layout[G]['height']
                too_high = (self.player.z  - self.player.zclimbmax*self.grid.scale) > -1*tile_height*self.grid.scale
                # TODO: make "too_high" a little higher than same height
                if too_high:
                    # Block the player from moving here
                    self.player.pos = (neighbor_x-1, pos[1])


    def update_mouse_height(self) -> None:
        """Mouse height is the top of the voxel where the mouse is hovering."""
        G = self.grid.xfm_pg(pygame.mouse.get_pos())
        voxels = self.voxel_artwork.layout
        h = 0
        if G in voxels:
            h = voxels[G]['height']
        # Store this height value for use elsewhere
        self.mouses['mouse_height'] = h

    # BELOW HERE IS RENDERING FOR DEBUG / DEV

    # NOT USED
    def render_mouse_location_as_white_circle(self) -> None:
        """Display mouse location with a white, transparent, hollow circle."""
        mpos_p = pygame.mouse.get_pos()                   # Mouse in pixel coord sys
        radius=10
        ### Surface((width, height), flags=0, Surface) -> Surface
        surf = pygame.Surface((2*radius,2*radius), flags=pygame.SRCALPHA)
        ### circle(surface, color, center, radius, width=0) -> Rect
        pygame.draw.circle(surf, Color(255,255,255,100), (radius,radius), radius, width=2)
        self.surfs['surf_game_art'].blit(surf, mpos_p, special_flags=pygame.BLEND_ALPHA_SDL2)

    # TODO: move this into VoxelArtwork
    # Called in VoxelArtwork.render()
    def render_grid_tile_highlighted_at_mouse(self) -> None:
        """Display mouse location by highlighting the grid square the mouse is hovering over."""
        G = self.grid.xfm_pg(pygame.mouse.get_pos())
        Gs = [ # Define a square tile on the grid
                (G[0]  ,G[1]  ),
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

    def render_debug_keystrokes(self, surf:pygame.Surface) -> None:
        """Show keystrokes in debug font at bottom of screen"""
        # Render keystrokes
        keystrokes = Text((0,0), font_size=20, sys_font="Roboto Mono")
        ### pygame.Surface.get_height() -> height
        ### pygame.font.Font.get_height() -> int
        keystrokes.pos = (surf.get_width()/2, surf.get_height() - keystrokes.font.get_height())
        cmdline = ":"
        keystrokes.update(cmdline + self.player.keystrokes)
        keystrokes.render(surf, self.colors['color_debug_keystrokes'])

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
        """Reset to initial view.

        - Define a 2x3 transform matrix [a,b,e;c,d,f] to go from g (game grid) to p (pixels)
        - Size the pixel artwork to center and fit within the window
        """
        self.a = 8
        self.b = 7
        self.c = 3
        self.d = -5

        # Define offset vector (in pixel coordinates)
        # Place origin at center of game art
        ctr = (int(self.game.os_window.size[0]/2),
               int(self.game.os_window.size[1]/2))
        self.e = ctr[0]
        self.f = ctr[1]

        self.pan_origin = (self.e, self.f) # Stores initial (e,f) during panning
        self.pan_ref = (None, None) # Stores initial mpos during panning
        self.is_panning = False # Tracks whether mouse is panning

        self.scale = self.zoom_to_fit()

    def zoom_to_fit(self) -> float:
        # Get the size of the grid
        size_g = (self.N, self.N)

        # Get an unscaled 2x2 transformation matrix
        a,b,c,d = self.a, self.b, self.c, self.d

        # Transform the size to pixel coordinates (as if the size were a point)
        size_p = (a*size_g[0] + b*size_g[1], c*size_g[0] + d*size_g[1])

        # Add some margin
        margin = 200
        size_p = (abs(size_p[0]) + margin, abs(size_p[1]) + margin)

        scale_x = self.game.os_window.size[0]/size_p[0]
        scale_y = self.game.os_window.size[1]/size_p[1]

        return min(scale_x, scale_y)

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

    def pan(self, mpos:tuple) -> None:
        self.e = self.pan_origin[0] + (mpos[0] - self.pan_ref[0])
        self.f = self.pan_origin[1] + (mpos[1] - self.pan_ref[1])

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

