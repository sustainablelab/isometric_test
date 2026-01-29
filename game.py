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
[x] Fix artifact: player "behind" voxel
    Frank and I think this is because player is not on grid.
    So see what happens after I fix that (player always on grid).
        This does not fix it.
    Otherwise, round player's position coordinate to next whole number to determine draw order. That should fix it.
        Yes, this fixes it. See "THIS FIXES THE ARTIFACT WHERE PLAYER IS HIDDEN BEHIND A VOXEL"
    I fixed another instance of this artifact. See "THIS FIXES YET ANOTHER ARTIFACT WHERE PLAYER IS BEHIND A VOXEL"
[x] Update self.pos_start anytime position is back on a tile
[x] Add controls for moving in discrete steps:
    [x] arrow keys and w,a,s,d become what h,j,k,l are now -- free movement
        [x] But end free movement on a tile: continue movement until character is on a tile
    [x] h,j,k,l become moving to discrete tiles
        [x] if the player is not on a discrete tile, this key puts them onto one
        [x] nudge the character -- change Shift+h,j,k,l to Alt+h,j,k,l-- this
            is just for dev so I have a way to nudge the character without
            collision detection rules 
            I made nudge, but it is broken now that I made discrete movement animated.
    [x] Apply collision detection to discrete movement
[x] Fix free movement so that changing direction between tiles does not leave player stuck off grid
    This is the same fix I used for discrete movement.
    In fact, I just turned 'update_movement_free' into a copy of 'update_movement_discrete'!
    The only difference is how key-up is handled.
[x] Fix free movement so that tapping movement keys does not get player stuck off grid
[x] Fix bug: rendering of player slow and messed up when there is only one voxel on the map
    * I was drawing the player over and over in the same frame if the player
      was at a grid location before the first voxel in the map.
    * The fix: check if the player has been rendered yet. Only render the player once.
LEFT OFF HERE
[ ] Add timers to identify where the FPS bottleneck is
[ ] Replace VoxelArtwork.render 'draw_index' with a simple check of the rounded grid coordinate
[ ] Clean up mouse rendering so I can easily measure how long it takes
[ ] * Add a 'z' value to tiles in tile_map.layout and voxels made from the tile_map
[ ] Fix player's shadow now that there is no default floor at z=0
[ ] Fix free movement and discrete movement for moving in two directions at the same time.
    * Discrete diagonal movement does this weird teleport bug
    * Free diagonal movement is lots of those weird teleport bugs
    * Free diagonal movement sometimes puts the player off grid
[ ] Refactor collision detection out to its own section
    [x] use keys dict to set a moves dict
    [ ] then handle collision detection in its own function that just uses the moves dict
[ ] Zoom centers on player or on center of screen, not on center of grid!

[x] Draw a floor
    [-] Give floor same color gradient effect that I put on the grid
    [ ] Move "ground floor" lower down:
        [ ] define how voxels combine to form a structure
        [ ] cover the floor in voxels
        [ ] make a second floor, third floor, etc.
[x] Add a Help HUD
[x] If Debug HUD is visible, show Help HUD below Debug HUD
[ ] Save game data
[ ] Load game data
[x] Improved collision detection using height:
    * Player traverses small height differences
    * Player is only blocked when height difference exceeds some amount
    * [x] Let mouse highlight "top" of a wall
    * [x] Left-click places player on "top" of a wall
    * [x] Player stays on top of the wall instead of falling through
    * [x] Player shadow is on the voxel (if any) under the player
    * [x] Player can walk off a wall
    * [x] Player can walk on a wall (need to consider height difference in collision detection)
    * [x] Player can walk up and down steps
[ ] Prototype spell-casting without using romanized chars as the UI
    * [ ] cast wall-related spells with dev shortcuts and mouse clicks
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
import time                                             # Profiling
from statistics import fmean                            # Profiling
import atexit
from pathlib import Path
from dataclasses import dataclass
import random
import json
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color
from libs.utils import setup_logging, load_image, OsWindow, Text, HelpHud, DebugHud, define_surfaces, define_actions, define_moves, define_held_keys, define_colors, define_settings, floor, ceiling, add, subtract, modulo

def shutdown() -> None:
    if logger: logger.info("Shutdown")
    # Clean up pygame
    pygame.font.quit()                                  # Uninitialize the font module
    pygame.quit()                                       # Uninitialize all pygame modules

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
    Wall(points=[(-2, -2), (-1, -2), (0, -2), (1, -2)], height=25, style='style_skeleton_frame')
    """
    points:list
    height:int
    # style:str = "style_shade_faces_solid_color"
    style:str = "style_skeleton_frame"

class Player:
    def __init__(self, game):
        self.game = game
        self.height = 10                                # Player height
        self.pos = (9.0,2.0)                            # Initial position of player
        self.pos_start = self.pos                       # Track starting position for discrete movement
        self.is_on_tile = True                          # Track if player is on the tile grid
        self.speed_walk = 0.2                           # Player walking speed
        self.speed_rise = 3.0                           # Player levitation speed
        self.wiggle = 0.1                               # Amount to randomize each coordinate value
        self.moving = False                             # Track moving or not moving
        self.moves = define_moves()                     # Dict of player movements
        # TODO: sign of z-direction always confuses me, e.g., look at self.z in render_romanized_chars
        self.z = 0                                      # Position in z-direction
        self.zclimbmax = 3.5                            # Max amt player can climb -- determines max height of steps
        self.dz = 0                                     # Speed in z-direction
        self.voxel = None                               # The voxel at the player's location (e.g., standing on a wall)
        self.is_casting = False
        self.spell = ""
        self.keystrokes = ""
        self.actions = define_actions()                 # Dict of player actions (what to do when Space is pressed)

    def update_actions(self) -> None:
        if self.actions['action_levitate']:
            self.dz = 0               # reset velocity (turn off gravity)
            self.z -= self.speed_rise # levitate

    def update_movement(self) -> None:
        # DEBUG moves
        if self.game.debug_hud:
            self.game.debug_hud.add_text(f"self.moves: {self.moves}")

        # Track moving or not moving for animation purposes
        if self.moves['move_down'] or self.moves['move_up'] or self.moves['move_left'] or self.moves['move_right']:
            self.moving = True
        else:
            self.moving = False

        if 1:
            if self.moves['move_down_to_tile'] or self.moves['move_down']:
                self.update_movement_state()
                self.update_movement_pos('down')
                self.handle_collision('down')
            if self.moves['move_up_to_tile'] or self.moves['move_up']:
                self.update_movement_state()
                self.update_movement_pos('up')
                self.handle_collision('up')
            if self.moves['move_left_to_tile'] or self.moves['move_left']:
                self.update_movement_state()
                self.update_movement_pos('left')
                self.handle_collision('left')
            if self.moves['move_right_to_tile'] or self.moves['move_right']:
                self.update_movement_state()
                self.update_movement_pos('right')
                self.handle_collision('right')
        else:
            self.update_movement_discrete()
            self.update_movement_free()


    # TODO: BUG: tap "s", then while player is still walking after I release
    # "s", press "w": player goes off-tile.
    # I think this happens because I end up in a state where self.pos_start
    # was set by "s", but I am now checking the "update_movement_pos" condition
    # based on pressing "w".
    def update_movement_discrete(self) -> None:
        # Handle discrete movement
        if self.moves['move_down_to_tile']:
            self.update_movement_state()
            self.update_movement_pos('down')
            self.handle_collision('down')
        if self.moves['move_up_to_tile']:
            self.update_movement_state()
            self.update_movement_pos('up')
            self.handle_collision('up')
        if self.moves['move_left_to_tile']:
            self.update_movement_state()
            self.update_movement_pos('left')
            self.handle_collision('left')
        if self.moves['move_right_to_tile']:
            self.update_movement_state()
            self.update_movement_pos('right')
            self.handle_collision('right')

    def update_movement_state(self) -> None:
        """If moving on a tile, player is now off the tile"""
        if self.is_on_tile:
            # Just started moving. Record initial position.
            self.pos_start = self.pos
            self.is_on_tile = False

    def update_movement_pos(self, direction:str) -> None:
        # Record position at start of this delta_t
        pos = self.pos
        move_the_entire_tile_in_one_tick = False
        match direction:

            case 'down':
                if move_the_entire_tile_in_one_tick:
                    self.pos = (pos[0],pos[1] - 1)
                else:
                    self.pos = (pos[0], subtract(pos[1], self.speed_walk))
                if self.pos[1] <= (self.pos_start[1] - 1):
                    # Clamp movement to next tile
                    self.pos = (self.pos_start[0],self.pos_start[1] - 1)
                    # Clear state
                    self.moves['move_down_to_tile'] = False
                    self.is_on_tile = True
                    self.pos_start = self.pos

            case 'up':
                if move_the_entire_tile_in_one_tick:
                    self.pos = (pos[0], pos[1] + 1)
                else:
                    self.pos = (pos[0], add(pos[1], self.speed_walk))
                if self.pos[1] >= (self.pos_start[1] + 1):
                    # Clamp movement to next tile
                    self.pos = (self.pos_start[0], self.pos_start[1] + 1)
                    # Clear state
                    self.moves['move_up_to_tile'] = False
                    self.is_on_tile = True
                    self.pos_start = self.pos

            case 'left':
                if move_the_entire_tile_in_one_tick:
                    self.pos = (pos[0] - 1 , pos[1])
                else:
                    self.pos = (subtract(pos[0], self.speed_walk), pos[1])
                if self.pos[0] <= (self.pos_start[0] - 1):
                    # Clamp movement to next tile
                    self.pos = (self.pos_start[0] - 1, self.pos_start[1])
                    # Clear state
                    self.moves['move_left_to_tile'] = False
                    self.is_on_tile = True
                    self.pos_start = self.pos

            case 'right':
                if move_the_entire_tile_in_one_tick:
                    self.pos = (pos[0] + 1 , pos[1])
                else:
                    self.pos = (add(pos[0], self.speed_walk), pos[1])
                if self.pos[0] >= (self.pos_start[0] + 1):
                    self.pos = (self.pos_start[0] + 1, self.pos_start[1])
                    self.moves['move_right_to_tile'] = False
                    self.is_on_tile = True
                    self.pos_start = self.pos

    def handle_collision(self, direction:str) -> None:
        match direction:

            case 'down':
                # Get coordinate of tile below player
                neighbor = (int(self.pos[0]), floor(self.pos[1]))
                if neighbor in self.game.tile_map.layout:
                    # There is a tile there.
                    if self.tile_is_too_high_to_walk_onto(neighbor):
                        # Block the player from moving here
                        self.pos = (self.pos[0], neighbor[1]+1)
                        # Clear state
                        self.moves['move_down_to_tile'] = False
                        self.is_on_tile = True

            case 'up':
                # Get coordinate of tile above player
                neighbor = (int(self.pos[0]), ceiling(self.pos[1]))
                if neighbor in self.game.tile_map.layout:
                    # There is a tile there.
                    if self.tile_is_too_high_to_walk_onto(neighbor):
                        # Block the player from moving here
                        self.pos = (self.pos[0], neighbor[1]-1)
                        # Clear state
                        self.moves['move_up_to_tile'] = False
                        self.is_on_tile = True

            case 'left':
                # Get coordinate of tile left of player
                neighbor = (floor(self.pos[0]), int(self.pos[1]))
                if neighbor in self.game.tile_map.layout:
                    # There is a tile there.
                    if self.tile_is_too_high_to_walk_onto(neighbor):
                        # Block the player from moving here
                        self.pos = (neighbor[0]+1, self.pos[1])
                        # Cleat state
                        self.moves['move_left_to_tile'] = False
                        self.is_on_tile = True

            case 'right':
                # Get coordinate of tile right of player
                neighbor = (ceiling(self.pos[0]), int(self.pos[1]))
                if neighbor in self.game.tile_map.layout:
                    # There is a tile there.
                    if self.tile_is_too_high_to_walk_onto(neighbor):
                        # Block the player from moving here
                        self.pos = (neighbor[0]-1, self.pos[1])
                        # Cleat state
                        self.moves['move_right_to_tile'] = False
                        self.is_on_tile = True

    def tile_is_too_high_to_walk_onto(self, tile:tuple) -> bool:
        """Return true if tile is too high to walk onto."""
        tile_height = self.game.voxel_artwork.layout[tile]['height']
        tile_z = self.game.voxel_artwork.layout[tile]['z']
        too_high = (self.z - self.zclimbmax*self.game.grid.scale) > (-1*(tile_z + tile_height)*self.game.grid.scale)
        return too_high

    def stop_all_movement(self) -> None:
        self.moves = define_moves()

    def update_movement_free(self) -> None:
        if self.moves['move_down']:
            self.update_movement_state()
            self.update_movement_pos('down')
            self.handle_collision('down')
        if self.moves['move_up']:
            self.update_movement_state()
            self.update_movement_pos('up')
            self.handle_collision('up')
        if self.moves['move_left']:
            self.update_movement_state()
            self.update_movement_pos('left')
            self.handle_collision('left')
        if self.moves['move_right']:
            self.update_movement_state()
            self.update_movement_pos('right')
            self.handle_collision('right')

    def old_update_movement_free(self) -> None:
        # TODO: if I tap 'w' and then tap 's' while mid-tile, I break the "end
        # on a tile behavior"... Why?
        #   Because 'move_down' and 'move_up' are both true.
        #   Another problem: the start_pos is messed up.
        # Handle free movement
        if self.moves['move_down']:
            self.update_movement_state()
            pos = self.pos; speed = self.speed_walk
            # Scale walking speed if moving DOWN+LEFT or DOWN+RIGHT
            if self.moves['move_left'] or self.moves['move_right']:
                speed *= 0.7
            # Set new position
            self.pos = (pos[0], subtract(pos[1], speed))
            # Collision detection
            neighbor_x = int(self.pos[0])
            # Going down? Look 1 tile "below" player
            # To look "below", comparison depends on whether player y is + or -
            if self.pos[1] < 0:
                # Example: player_y = -10.8, 1 tile below y=-11
                neighbor_y = int(self.pos[1]) - 1
            else:
                # Example: player_y = +10.8, 1 tile below y=+10
                neighbor_y = int(self.pos[1])
            if (neighbor_x,neighbor_y) in self.game.tile_map.layout:
                # There is a tile there.
                # Now check if the top of this tile is too high for the player to get onto
                G = (neighbor_x, neighbor_y)
                tile_height = self.game.voxel_artwork.layout[G]['height']
                too_high = (self.z  - self.zclimbmax*self.game.grid.scale) > (-1*tile_height*self.game.grid.scale)
                # TODO: make "too_high" a little higher than same height
                if too_high:
                    # Block the player from moving here
                    self.pos = (pos[0], neighbor_y+1)
            # Check if player is back on the tile grid
            dy = subtract(self.pos_start[1], self.pos[1])
            ry = modulo(dy,1)
            if ry == 0:
                self.is_on_tile = True
                self.pos_start = self.pos

        if self.moves['move_up']:
            self.update_movement_state()
            pos = self.pos; speed = self.speed_walk
            # Scale walking speed if moving UP+LEFT or UP+RIGHT
            if self.moves['move_left'] or self.moves['move_right']:
                speed *= 0.7
            # Set new position
            self.pos = (pos[0], add(pos[1], speed))
            # Collision detection
            neighbor_x = int(self.pos[0])
            # Going up? Look 1 tile "above" player
            if self.pos[1] < 0:
                # Example: player_y = -10.8, 1 tile above y=-10
                neighbor_y = int(self.pos[1])
            else:
                # Example: player_y = +10.8, 1 tile above y=+11
                neighbor_y = int(self.pos[1]) + 1
            # for wall in self.tile_map.walls:
            #     if (neighbor_x,neighbor_y) in wall.points:
            #         self.player.pos = (pos[0], neighbor_y-1)
            if (neighbor_x,neighbor_y) in self.game.tile_map.layout:
                # There is a tile there.
                # Now check if the top of this tile is too high for the player to get onto
                G = (neighbor_x, neighbor_y)
                tile_height = self.game.voxel_artwork.layout[G]['height']
                too_high = (self.z  - self.zclimbmax*self.game.grid.scale) > (-1*tile_height*self.game.grid.scale)
                # TODO: make "too_high" a little higher than same height
                if too_high:
                    # Block the player from moving here
                    self.pos = (pos[0], neighbor_y-1)
            # Check if player is back on the tile grid
            dy = subtract(self.pos_start[1], self.pos[1])
            ry = modulo(dy,1)
            if ry == 0:
                self.is_on_tile = True
                self.pos_start = self.pos

        if self.moves['move_left']:
            pos = self.pos
            speed = self.speed_walk
            # Scale walking speed if moving LEFT+UP or LEFT+DOWN
            if self.moves['move_up'] or self.moves['move_down']:
                speed *= 0.7
            self.pos = (subtract(pos[0], speed),  pos[1])
            # Collision detection
            neighbor_y = int(self.pos[1])
            if self.pos[0] < 0:
                # Example: Player_x = -10.8, 1 tile left x=-11
                neighbor_x = int(self.pos[0] - 1)
            else:
                # Example player_x = +10.8, 1 tile left x=+10
                neighbor_x = int(self.pos[0])
            # for wall in self.tile_map.walls:
            #     if (neighbor_x,neighbor_y) in wall.points:
            #         self.player.pos = (neighbor_x+1, pos[1])
            if (neighbor_x,neighbor_y) in self.game.tile_map.layout:
                # There is a tile there.
                # Now check if the top of this tile is too high for the player to get onto
                G = (neighbor_x, neighbor_y)
                tile_height = self.game.voxel_artwork.layout[G]['height']
                too_high = (self.z  - self.zclimbmax*self.game.grid.scale) > -1*tile_height*self.game.grid.scale
                # TODO: make "too_high" a little higher than same height
                if too_high:
                    # Block the player from moving here
                    self.pos = (neighbor_x+1, pos[1])

        if self.moves['move_right']:
            pos = self.pos
            speed = self.speed_walk
            # Scale walking speed if moving RIGHT+UP or RIGHT+DOWN
            if self.moves['move_up'] or self.moves['move_down']:
                speed *= 0.7
            self.pos = (add(pos[0], speed),  pos[1])
            # Collision detection
            neighbor_y = int(self.pos[1])
            if self.pos[0] < 0:
                # Example: Player_x = -10.8, 1 tile right x=-10
                neighbor_x = int(self.pos[0])
            else:
                # Example player_x = +10.8, 1 tile right x=+11
                neighbor_x = int(self.pos[0] + 1)
            # for wall in self.tile_map.walls:
            #     if (neighbor_x,neighbor_y) in wall.points:
            #         self.player.pos = (neighbor_x-1, pos[1])
            if (neighbor_x,neighbor_y) in self.game.tile_map.layout:
                # There is a tile there.
                # Now check if the top of this tile is too high for the player to get onto
                G = (neighbor_x, neighbor_y)
                tile_height = self.game.voxel_artwork.layout[G]['height']
                too_high = (self.z  - self.zclimbmax*self.game.grid.scale) > -1*tile_height*self.game.grid.scale
                # TODO: make "too_high" a little higher than same height
                if too_high:
                    # Block the player from moving here
                    self.pos = (neighbor_x-1, pos[1])


    def update_voxel(self) -> None:
        """Figure out which voxel (if any) is below the player."""
        # G = (int(self.pos[0]), int(self.pos[1])) # No, don't just integer truncate
        # If partway between voxels, use whichever voxel player is closer to
        G = (round(self.pos[0]), round(self.pos[1]))
        tiles = self.game.tile_map.layout
        voxels = self.game.voxel_artwork.layout
        if G in tiles:
            self.voxel = voxels[G]
        else:
            self.voxel = None # Nothing under the player

    def render(self, surf:pygame.Surface) -> None:
        """Display the player."""
        self.game.timer_draw_player.start()
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
            tile_height = self.voxel['height']
            tile_z = self.voxel['z']
            floor_height = -1*(tile_z + tile_height)*self.game.grid.scale
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
        self.game.timer_draw_player.stop()

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

        elif 0:
            ### Make floor tiles
            layout[(0,0)] = {'z':3,  'percentage':1.0, 'height':6, 'style':"style_floor_tiles", 'rand_amt':0}
            layout[(0,-1)] = {'z':0, 'percentage':1.0, 'height':3, 'style':"style_floor_tiles", 'rand_amt':0}
            layout[(0,-2)] = {'z':-3,'percentage':1.0, 'height':3, 'style':"style_floor_tiles", 'rand_amt':0}
            layout[(0,-3)] = {'z':-6,'percentage':1.0, 'height':3, 'style':"style_floor_tiles", 'rand_amt':0}
            layout[(0,-4)] = {'z':-9,'percentage':1.0, 'height':3, 'style':"style_floor_tiles", 'rand_amt':0}
        else:
            ### Make walls
            # Outer walls
            for i in range(a,b):
                layout[(i,  a)]   = {'z':0, 'percentage':1, 'height':25, 'style':"style_shade_faces_solid_color", 'rand_amt':5} # Front left wall
                layout[(i,  b-1)] = {'z':0, 'percentage':1, 'height':65, 'style':"style_shade_faces_solid_color", 'rand_amt':5} # Back right wall
                layout[(a,  i)]   = {'z':0, 'percentage':1, 'height':65, 'style':"style_shade_faces_solid_color", 'rand_amt':5} # Back left wall
                layout[(b-1,i)]   = {'z':0, 'percentage':1, 'height':25, 'style':"style_skeleton_frame", 'rand_amt':5} # Front right wall
            # Inner walls: walls at constant x from y=a to y=b and constant y from x=a to x=b
            x = -10; a = -10; b = 20
            for i in range(a,b):
                layout[(x,i)] = {'z':0, 'percentage':1, 'height':5, 'style':"style_shade_faces_solid_color", 'rand_amt':5}
            y = 20; a = -10; b = 20
            for i in range(a,b):
                layout[(i,y)] = {'z':0, 'percentage':1, 'height':5, 'style':"style_shade_faces_solid_color", 'rand_amt':5}
            x = -5; a = -10; b = 15
            for i in range(a,b):
                layout[(x,i)] = {'z':0, 'percentage':1, 'height':5, 'style':"style_shade_faces_solid_color", 'rand_amt':5}
            y = 15; a = -5; b = 20
            for i in range(a,b):
                layout[(i,y)] = {'z':0, 'percentage':1, 'height':5, 'style':"style_shade_faces_solid_color", 'rand_amt':5}
            ### Make stairs
            # Make right-hand staircase up to back corner
            step_height = 0
            start = 4
            for i in range(-1*start, self.a, -1):
                step_height += 3
                layout[(i,self.b-2)] = {'z':0, 'percentage':1, 'height':step_height, 'style':"style_shade_faces_solid_color", 'rand_amt':0}
            # Make left-hand staircase up to back corner
            step_height = 0
            for i in range(start-1, self.b-2):
                step_height += 3
                layout[(self.a+1,i)] = {'z':0, 'percentage':1, 'height':step_height, 'style':"style_shade_faces_solid_color", 'rand_amt':0}
            # Fill the rest of the layout with floor tiles
            grid_list = [] # Walk grid coordinates
            a = self.a; b = self.b
            for j in range(b,a-1,-1): # See VoxelArtwork.render()
                for i in range(a,b):
                    G = (i,j)
                    grid_list.append(G)
            ### [(-25,  25), (-24,  25), ... (0,  25), ... (24,  25),
            ###  (-25,  24), (-24,  24), ... (0,  24), ... (24,  24),
            ###  ...
            ###  (-25, -25), (-24, -25), ... (0, -25), ... (24, -25)]
            for G in grid_list:
                if G in layout:
                    pass # Don't need a floor tile here yet because I am doing just one voxel per tile for now
                else:
                    # No voxel here yet: put a floor tile here
                    # TODO: find a way to randomize the tiles a little, but not too much.
                    # rand_amt:1 is imperceptible and rand_amt:2 is too much.
                    layout[G] = {'z':-2, 'percentage':0.95, 'height':2, 'style':"style_floor_tiles", 'rand_amt':1}

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
            voxel_artwork[G] = {'z':wall['z'], 'percentage':wall['percentage'], 'grid_points':grid_points, 'height':height, 'style':wall['style']}
            # See "adjust_voxel_size" and "Draw voxels!"
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
        # p = 1-self.percentage
        # d = p/2
        # Convert each voxel to pixel coordinates and render
        # TODO: rename self.layout to self.voxel_dict or something more descriptive
        for G in self.layout:
            Gs = self.layout[G]['grid_points']
            # Copy height and style
            z = self.layout[G]['z']
            height = self.layout[G]['height']
            style = self.layout[G]['style']
            p = 1 - self.layout[G]['percentage']
            # p = 1 - self.percentage
            d = p/2
            adjusted_grid_points = [
                    (Gs[0][0] + d, Gs[0][1] + d),
                    (Gs[1][0] - d, Gs[1][1] + d),
                    (Gs[2][0] - d, Gs[2][1] - d),
                    (Gs[3][0] + d, Gs[3][1] - d)
                    ]
            # Apply self.percentage and keep the voxel centered on the tile
            adjusted_voxel_artwork[G] = {'z':z, 'grid_points':adjusted_grid_points,'height':height,'style':style}
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
        """Render voxels, player, and mouse.

        TODO: why do I use a 'draw_index'? Why not just check if the rounded
        grid coordinates match the current grid coordinate? And remember to
        have checks in the beginning and at the end to catch if the player or
        mouse is off-grid.
        """
        voxels = self.adjust_voxel_size()
        player = self.game.player
        player_is_rendered = False
        mouse_is_rendered = False
        # Why do I track if the player is rendered yet?
        #   Say there are NO VOXELS on the grid until about the middle of the grid.
        #   Then 'voxel_index' will be 0 for a long time while I iterate over the list of grid points.
        #   Say the player is at voxel_index 0 or 1 or whatever.
        #   Then the player will be drawn over and over and over again until that first voxel is finally drawn.
        #   This tanks the framerate! And it superimposes many images of the player onto the same frame.
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
                # if (player.pos[0] >= G[0]) and (player.pos[1] <= G[1]): # NO!
                # 'round(player.pos[n])' -- THIS FIXES THE ARTIFACT WHERE PLAYER IS HIDDEN BEHIND A VOXEL
                if (round(player.pos[0]) >= G[0]) and (round(player.pos[1]) <= G[1]):
                    # Player is in front of this voxel; update draw order
                    player_draw_index = voxel_index + 1
                if (mouse[0] >= G[0]) and (mouse[1] <= G[1]):
                    mouse_draw_index = voxel_index + 1
                # Increment voxel index at the end of the loop (not the beginning)!
                #   THIS FIXES YET ANOTHER ARTIFACT WHERE PLAYER IS BEHIND A VOXEL
                voxel_index += 1

        ### Draw voxels!
        voxel_index = 0 # draw_index
        for G in grid_list:
            if G in voxels:
                ### Draw voxel
                # Convert the base quad grid points (see make_voxels_from_tile_map) to pixel points
                #
                # grid_points -- list of four grid coordinates
                #     The intent is these coordinates are the vertices of a rectangular
                #     grid tile. The four coordinates are listed going clockwise around
                #     the rectangle starting at the "lower left" of the rectangle.
                #
                # Xfm the four grid points to pixel space
                _Ps = [self.game.grid.xfm_gp(grid_point) for grid_point in voxels[G]['grid_points']]
                # Adjust the z-location of these four points
                z = voxels[G]['z']
                Ps = [(P[0],P[1] - z*self.game.grid.scale) for P in _Ps]
                # Describe the three visible surfaces of the voxel as quads
                ### T: Top, L: Left, R: Right
                height = voxels[G]['height']
                voxel_Ts = [(P[0],P[1] - height*self.game.grid.scale) for P in Ps]
                voxel_Ls = [Ps[0], Ps[1], voxel_Ts[1], voxel_Ts[0]]
                voxel_Rs = [Ps[1], Ps[2], voxel_Ts[2], voxel_Ts[1]]
                style = voxels[G]['style']
                match style:
                    case "style_floor_tiles":
                        if self.game.settings['setting_render_floor_tiles']:
                            pygame.draw.polygon(surf, self.game.colors['color_voxel_top_floor'], voxel_Ts)
                            pygame.draw.polygon(surf, self.game.colors['color_voxel_left_floor'], voxel_Ls)
                            pygame.draw.polygon(surf, self.game.colors['color_voxel_right_floor'], voxel_Rs)
                    case "style_shade_faces_solid_color":
                        # Render the three visible quads
                        ### polygon(surface, color, points) -> Rect
                        pygame.draw.polygon(surf, self.game.colors['color_voxel_top'], voxel_Ts)
                        pygame.draw.polygon(surf, self.game.colors['color_voxel_left'], voxel_Ls)
                        pygame.draw.line(surf, self.game.colors['color_voxel_left_shadow'], voxel_Ls[0], voxel_Ls[1],width=3)
                        pygame.draw.polygon(surf, self.game.colors['color_voxel_right'], voxel_Rs)
                        pygame.draw.line(surf, self.game.colors['color_voxel_right_shadow'], voxel_Rs[0], voxel_Rs[1],width=3)
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
                    pygame.draw.polygon(surf, Color(200,200,100), voxel_Ts)
                    points_z = [(P[0], P[1] - z*self.game.grid.scale) for P in _Ps]
                    # Draw a yellow highlight on the top and bottom faces of the voxel
                    pygame.draw.polygon(surf, Color(200,200,100), points_z, width=3)
                # Increment voxel index at the end of the loop (not the beginning)!
                #   THIS FIXES YET ANOTHER ARTIFACT WHERE PLAYER IS BEHIND A VOXEL
                voxel_index += 1
            # TODO: do not draw green highlight if drawing a yellow highlight
            # Check draw order for mouse
            if voxel_index == mouse_draw_index:
                if not mouse_is_rendered:
                    # Draw the mouse green highlight on the grid
                    self.game.render_grid_tile_highlighted_at_mouse()
                    mouse_is_rendered = True
            # Check draw order for player
            if voxel_index == player_draw_index:
                if not player_is_rendered:
                    # Draw player
                    player.render(surf)
                    player_is_rendered = True
            # Draw front part of mouse green highlight in front of player if they are at the same index
            if (mouse[0] >= round(player.pos[0])) and (mouse[1] <= round(player.pos[1])):
                self.game.render_grid_tile_highlighted_at_mouse_around_player()
        # DEBUG
        ### DebugHud.add_text(debug_text:str)
        if self.game.debug_hud:
            self.game.debug_hud.add_text(f"player_draw_index: {player_draw_index}")
            self.game.debug_hud.add_text(f"mouse_draw_index: {mouse_draw_index}")
            self.game.debug_hud.add_text(f"len(voxels): {len(voxels)}")
            self.game.debug_hud.add_text(
                    f"player.pos: ({player.pos[0]:.1f},{player.pos[1]:.1f},z={player.z:.1f})")

        # If mouse is in front of all voxels, player has not been drawn yet!
        if mouse_draw_index >= len(voxels):
            if not mouse_is_rendered:
                self.game.render_grid_tile_highlighted_at_mouse()
                mouse_is_rendered = True
        # If player is in front of all voxels, player has not been drawn yet!
        if player_draw_index >= len(voxels):
            if not player_is_rendered:
                # Draw the player now
                player.render(surf)
                player_is_rendered = True

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

class TimerFifo:
    """Buffer readings of Timer.elapsed and report the mean.

    >>> fifo = TimerFifo()
    >>> fifo.update(5)
    >>> fifo.mean
    5.0
    >>> fifo.update(6)
    >>> fifo.mean
    5.5
    """
    def __init__(self, size:int=10) -> None:
        self.size = size
        self.readings = [0]*self.size # Save buffered values in list 'readings'
        self.num_readings = 0 # Track how many readings so far (max out at self.size)
        self.data = None

    def update(self, reading) -> None:
        self.readings.pop()
        self.readings.insert(0,reading)
        self.num_readings = min(self.size, self.num_readings + 1)
        self.data = self.readings[0:self.num_readings]

    @property
    def mean(self) -> float:
        if self.data: return fmean(self.data)
        else: return 0 # Fifo is not used (made a Timer, but never timed anything with it)

class Timer:
    def __init__(self, game) -> None:
        self.game = game
        self.time_start=0
        self.time_stop=0
        self.fifo = TimerFifo(size=10)

    def start(self) -> None:
        self.time_start = time.time()

    def stop(self) -> None:
        """Stop the timer and record elapsed time in the FIFO buffer."""
        self.time_stop = time.time() # Stop timer
        self.fifo.update(self.time_stop - self.time_start) # Record elapsed time

    @property
    def elapsed(self) -> int:
        """Return the mean elapsed time."""
        return self.fifo.mean

    def debug_hud_report(self, name:str) -> None:
        """Report timer in debug HUD."""
        t = self.elapsed                                # Time
        p = (t/self.game.timer_game_loop.elapsed)*100   # Percentage
        self.game.debug_hud.add_text(f"{name:32}: {p:3.0f}% {t*1000:0.1f}ms")

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
        # self.moves = define_moves()                     # Dict of player movements
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
        self.mouses = {'mouse_height': 0, 'mouse_z':0}

        # FPS
        self.clock = pygame.time.Clock()

        # Profiling
        self.timer_game_loop = Timer(self)
        self.timer_update_gravity_effects = Timer(self)
        self.timer_draw_voxel_artowrk_and_player = Timer(self)
        self.timer_draw_debug_grid = Timer(self)
        self.timer_draw_player = Timer(self)
        self.timer_player_update_voxel = Timer(self)
        self.timer_update_mouse_height = Timer(self)
        self.timer_blit_to_os_window = Timer(self)

    def run(self):
        while True: self.game_loop()

    def game_loop(self):
        # Create the debug HUD
        if self.settings['setting_debug']:
            self.debug_hud = DebugHud(self)
            self.add_debug_text()
        else:
            self.debug_hud = None
        self.timer_game_loop.start()
        self.timer_update_gravity_effects.start()


        # Update things affected by gravity
        self.update_gravity_effects()
        self.timer_update_gravity_effects.stop()

        # Handle keyboard and mouse
        # Zoom by scrolling the mouse wheel
        # Pan by pressing the mouse wheel or left-clicking
        self.handle_ui_events()
        if self.grid.is_panning:
            self.grid.pan(pygame.mouse.get_pos())

        self.update_held_keys_effects()
        # self.update_player_actions()
        self.player.update_actions()
        self.player.update_movement()
        if self.debug_hud:
            dy = subtract(self.player.pos_start[1], self.player.pos[1])
            ry = modulo(dy,1)
            dx = subtract(self.player.pos_start[0], self.player.pos[0])
            rx = modulo(dx,1)
            self.debug_hud.add_text(f"self.player.pos: {self.player.pos}")
            self.debug_hud.add_text(f"dx%1: {rx%1}, dy%1: {ry}")


        self.timer_draw_voxel_artowrk_and_player.start()
        # Clear screen
        ### fill(color, rect=None, special_flags=0) -> Rect
        self.surfs['surf_game_art'].fill(self.colors['color_game_art_bgnd'])

        # Draw the layout of voxels and player
        self.voxel_artwork.render(self.surfs['surf_game_art'])
        self.timer_draw_voxel_artowrk_and_player.stop()

        draw_debug_grid = False
        if draw_debug_grid:
            # Draw grid
            self.timer_draw_debug_grid.start()
            if self.settings['setting_debug']:
                self.grid.draw(self.surfs['surf_game_art'])
            self.timer_draw_debug_grid.stop()

        # Figure out which voxel is below the player
        self.timer_player_update_voxel.start()
        self.player.update_voxel()
        self.timer_player_update_voxel.stop()

        # self.render_mouse_location_as_white_circle()
        # Use the power of xfm_gp()
        # self.render_grid_tile_highlighted_at_mouse()
        self.timer_update_mouse_height.start()
        self.update_mouse_height()
        self.timer_update_mouse_height.stop()

        ### TEMPORARY: spell casting
        # Display typing text while casting
        if self.player.is_casting:
            # Display romanized chars above player if spell casting
            self.player.render_romanized_chars(self.surfs['surf_game_art'])
            # Display keystrokes at bottom of screen in debug font
            self.render_debug_keystrokes(self.surfs['surf_game_art'])

        # # TEMPORARY: Draw a floor as a single giant square
        # TODO: To "slice" a transparent plane like this through the art, I
        # have to render things BELOW THE FLOOR before I draw the floor and
        # things ABOVE THE FLOOR after I draw the floor!
        # a = self.tile_map.a
        # b = self.tile_map.b
        # points = [self.grid.xfm_gp(G) for G in [(a,a), (b,a), (b,b), (a,b)]]
        # ### polygon(surface, color, points) -> Rect
        # pygame.draw.polygon(self.surfs['surf_alpha'], self.colors['color_floor_solid'], points)
        # self.surfs['surf_game_art'].blit(self.surfs['surf_alpha'], (0,0), special_flags=pygame.BLEND_ALPHA_SDL2)
        # self.surfs['surf_alpha'].fill(self.colors['color_clear'])

        # Copy game art to OS window: 8%
        ### blit(source, dest, area=None, special_flags=0) -> Rect
        self.timer_blit_to_os_window.start()
        self.surfs['surf_os_window'].blit(self.surfs['surf_game_art'], (0,0))
        self.timer_blit_to_os_window.stop()


        # Display Debug HUD overlay
        if self.debug_hud:
            self.debug_hud.render(self.colors['color_debug_hud'])

        # Display HELP below DEBUG
        if self.settings['setting_show_help']:
            self.help_hud = HelpHud(self)
            self.help_hud.add_text("View:")
            self.help_hud.add_text("  - Roll mouse wheel: zoom")
            self.help_hud.add_text("  - Click wheel and drag: pan")
            self.help_hud.add_text("  - Shift+left-click and drag: pan")
            self.help_hud.add_text("  - 'r': reset view")
            self.help_hud.add_text("Player:")
            self.help_hud.add_text("  - 'Left-click': place player")
            self.help_hud.add_text("  - 'Space': levitate player")
            self.help_hud.add_text("Discrete Movement:")
            self.help_hud.add_text("  - 'j,k': player down/up (Shift: nudge)")
            self.help_hud.add_text("  - 'h,l': player left/right (Shift: nudge)")
            self.help_hud.add_text("Free Movement:")
            self.help_hud.add_text("  - 'w,a,s,d': player up/left/down/right")
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

        self.timer_game_loop.stop()

        ### clock.tick(framerate=0) -> milliseconds
        self.clock.tick(60)

    def add_debug_text(self) -> None:
        # Report total time (ms) elapsed in game loop
        self.debug_hud.add_text(                            f"| Game loop: {self.timer_game_loop.elapsed*1000:0.1f}ms")
        # Report percentage of total and time (ms) for parts of the game loop
        self.timer_update_gravity_effects.debug_hud_report( "|  update_gravity_effects()")
        self.timer_draw_voxel_artowrk_and_player.debug_hud_report("|  draw voxel artwork and player")
        self.timer_draw_player.debug_hud_report(            "|    draw player")
        self.timer_draw_debug_grid.debug_hud_report(        "|  draw debug grid")
        self.timer_player_update_voxel.debug_hud_report(    "|  player.update_voxel")
        self.timer_update_mouse_height.debug_hud_report(    "|  update_mouse_height")
        self.timer_blit_to_os_window.debug_hud_report(      "|  blit_to_os_window")
        mpos_p = pygame.mouse.get_pos()                   # Mouse in pixel coord sys
        mpos_g = self.grid.xfm_pg(mpos_p)
        # Display mouse coordinates in game grid coordinate system
        self.debug_hud.add_text(f"Mouse (grid): {mpos_g}")
        # Display percentage each voxel is filled
        self.debug_hud.add_text(f"Voxel %: {int(100*self.voxel_artwork.percentage)}%")
        # Which voxel is below the player
        self.debug_hud.add_text(f"self.player.voxel: {self.player.voxel}")
        # Get height at mouse in game coordinates
        self.debug_hud.add_text(f"self.mouses['mouse_z']: {self.mouses['mouse_z']}")
        self.debug_hud.add_text(f"self.mouses['mouse_height']: {self.mouses['mouse_height']}")
        # Debug discrete motion
        pos_start = self.player.pos_start
        self.debug_hud.add_text(f"self.player.pos_start: ({pos_start[0]},{pos_start[1]}), "
                                f"self.player.is_on_tile: {self.player.is_on_tile}")
        # Display transform matrix element values a,b,c,d,e,f
        a,b,c,d = self.grid.scaled()
        e,f = (self.grid.e, self.grid.f)
        self.debug_hud.add_text(f"a: {a:0.1f} | b: {b:0.1f} | c: {c:0.1f} | d: {d:0.1f} | e: {e:0.1f} | f: {f:0.1f}")
        ### TEMPORARY: spell casting
        # DEBUG: What spell is cast?
        if self.player.spell != "":
            self.debug_hud.add_text(f"Cast: {self.player.spell}")

    def update_gravity_effects(self) -> None:
        # Account for gravity
        self.player.dz = min(self.max_fall_speed, self.player.dz+self.gravity) # acceleration updates velocity
        self.player.z += self.player.dz                 # velocity updates position

        # Stop falling if player is standing on something
        # floor_height = 0 # Imaginary floor!
        floor_height = 1000*self.grid.scale # Earth ground
        if self.player.voxel != None:
            tile_height = self.player.voxel['height']
            tile_z = self.player.voxel['z']
            floor_height_g = tile_z + tile_height
            floor_height = -1*floor_height_g*self.grid.scale
            if self.debug_hud:
                self.debug_hud.add_text(f"floor_height: {floor_height_g} [game]")
                self.debug_hud.add_text(f"floor_height: {floor_height} [pixels]")
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
                                self.handle_mousebuttondown_leftclick(event)
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

    def handle_mousebuttondown_leftclick(self, event) -> None:
        """Place the player"""
        self.player.pos = self.grid.xfm_pg(event.pos)
        self.player.z = -1*self.grid.scale*self.mouses['mouse_height']
        self.player.stop_all_movement()
        self.player.pos_start = self.player.pos
        self.player.is_on_tile = True

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
            self.handle_keyup_movement(event)
            self.handle_keyup_other(event)

    def handle_keyup_movement(self, event) -> None:
        """Continue to move player until player is on tile"""
        kmod = pygame.key.get_mods()
        match event.key:

            case pygame.K_s: # Release 's' (was moving down)
                self.keys['key_s'] = False
                if self.keys['key_w']: # Player holds down 's' and 'w' and releases 's'
                    pass
                else: # Player holds down 's' and releases 's' ('w' was not held down)
                    if not self.player.is_on_tile:
                        # Set "start" position to nearest tile
                        self.player.pos_start = (self.player.pos[0], round(self.player.pos[1]))
                        self.player.moves['move_down_to_tile'] = True

            case pygame.K_w: # Release 'w' (was moving up)
                self.keys['key_w'] = False
                if self.keys['key_s']: # Player holds down 'w' and 's' and releases 'w'
                    pass
                else: # Player holds down 'w' and releases 'w' ('s' was not held down)
                    if not self.player.is_on_tile:
                        # Set "start" position to nearest tile
                        self.player.pos_start = (self.player.pos[0], round(self.player.pos[1]))
                        self.player.moves['move_up_to_tile'] = True

            case pygame.K_a: # Release 'a' (was moving left)
                self.keys['key_a'] = False
                if self.keys['key_d']: # Player holds down 'a' and 'd' and releases 'a'
                    pass
                else: # Player holds down 'a' and releases 'a' ('d' was not held down)
                    if not self.player.is_on_tile:
                        # Set "start" position to nearest tile
                        self.player.pos_start = (round(self.player.pos[0]), self.player.pos[1])
                        self.player.moves['move_left_to_tile'] = True

            case pygame.K_d: # Release 'd' (was moving right)
                self.keys['key_d'] = False
                if self.keys['key_a']: # Player holds down 'd' and 'a' and releases 'd'
                    pass
                else: # Player holds down 'd' and releases 'd' ('a' was not held down)
                    if not self.player.is_on_tile:
                        # Set "start" position to nearest tile
                        self.player.pos_start = (round(self.player.pos[0]), self.player.pos[1])
                        self.player.moves['move_right_to_tile'] = True

            case _: pass

    def handle_keyup_other(self, event) -> None:
        kmod = pygame.key.get_mods()
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
            case pygame.K_F3:                           # F2 - Toggle Debug
                self.settings['setting_render_floor_tiles'] = not self.settings['setting_render_floor_tiles']
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
                self.player.moves['move_down_to_tile'] = True
                # If already moving up, stop moving up
                if self.player.moves['move_up_to_tile']:
                    # Was going up, then pressed 'j' before getting to next tile
                    self.player.moves['move_up_to_tile'] = False
                    # Go back to the tile you were on when you started moving up
                    start = self.player.pos_start
                    self.player.pos_start = (start[0], start[1]+1)
            case pygame.K_k:
                self.player.moves['move_up_to_tile'] = True
                # If already moving down, stop moving down
                if self.player.moves['move_down_to_tile']:
                    # Was going down, then pressed 'k' before getting to next tile
                    self.player.moves['move_down_to_tile'] = False
                    # Go back to the tile you were on when you started moving down
                    start = self.player.pos_start
                    self.player.pos_start = (start[0], start[1]-1)
            case pygame.K_h:
                self.player.moves['move_left_to_tile'] = True
                # If already moving right, stop moving right
                if self.player.moves['move_right_to_tile']:
                    # Was going right, then pressed 'h' before getting to next tile
                    self.player.moves['move_right_to_tile'] = False
                    # Go back to the tile you were on when you started moving right
                    start = self.player.pos_start
                    self.player.pos_start = (start[0]+1,start[1])
            case pygame.K_l:
                self.player.moves['move_right_to_tile'] = True
                # If already moving left, stop moving left
                if self.player.moves['move_left_to_tile']:
                    # Was going left, then pressed 'l' before getting to next tile
                    self.player.moves['move_left_to_tile'] = False
                    # Go back to the tile you were on when you started moving left
                    start = self.player.pos_start
                    self.player.pos_start = (start[0]-1,start[1])
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
                if kmod & pygame.KMOD_SHIFT: # DEV
                    # 'Shift+J' nudges player
                    pos = self.player.pos
                    self.player.pos = (pos[0], subtract(pos[1], self.player.speed_walk))
                else: # GAME
                    self.keys['key_s'] = True
                    if self.player.moves['move_up_to_tile']:
                        # Was going up, then released 'w' and tapped 's' before getting to next tile
                        self.player.moves['move_up_to_tile'] = False
                        # Go back to the last tile you were on while moving up
                        start = self.player.pos_start
                        self.player.pos_start = (start[0], start[1]+1)

            case pygame.K_w: # Move Up
                if kmod & pygame.KMOD_SHIFT: # DEV
                    # 'Shift+K' nudges player
                    pos = self.player.pos
                    self.player.pos = (pos[0], add(pos[1], self.player.speed_walk))
                else: # GAME
                    self.keys['key_w'] = True
                    if self.player.moves['move_down_to_tile']:
                        # Was going down, then released 's' and tapped 'w' before getting to next tile
                        self.player.moves['move_down_to_tile'] = False
                        # Go back to the last tile you were on while moving down
                        start = self.player.pos_start
                        self.player.pos_start = (start[0], start[1]-1)

            case pygame.K_a: # Move Left
                if kmod & pygame.KMOD_SHIFT: # DEV
                    # 'Shift+H' nudges player
                    pos = self.player.pos
                    self.player.pos = (subtract(pos[0], self.player.speed_walk),  pos[1])
                else: # GAME
                    self.keys['key_a'] = True
                    if self.player.moves['move_right_to_tile']:
                        # Was going right, then released 'd' and tapped 'a' before getting to next tile
                        self.player.moves['move_right_to_tile'] = False
                        # Go back to the last tile you were on while moving right
                        start = self.player.pos_start
                        self.player.pos_start = (start[0]+1,start[1])
                        # self.player.pos_start = (start[0],start[1])

            case pygame.K_d: # Move Right
                if kmod & pygame.KMOD_SHIFT: # DEV
                    # 'Shift+L' nudges player
                    pos = self.player.pos
                    self.player.pos = (add(pos[0], self.player.speed_walk),  pos[1])
                else: # GAME
                    self.keys['key_d'] = True
                    if self.player.moves['move_left_to_tile']:
                        # Was going left, then released 'a' and tapped 'd' before getting to next tile
                        self.player.moves['move_left_to_tile'] = False
                        # Go back to the last tile you were on while moving left
                        start = self.player.pos_start
                        self.player.pos_start = (start[0]-1,start[1])
                        # self.player.pos_start = (start[0],start[1])

            case _:
                pass


    def update_held_keys_effects(self) -> None:
        self.update_held_keys_effects_grid_xfm()
        self.update_held_keys_effects_player_movement()

        # Pick what action to do when Space is held
        self.player.actions['action_levitate'] = self.keys['key_Space']

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
        self.player.moves['move_down']  = self.keys['key_s']
        self.player.moves['move_up']    = self.keys['key_w']
        self.player.moves['move_left']  = self.keys['key_a']
        self.player.moves['move_right'] = self.keys['key_d']

    def update_mouse_height(self) -> None:
        """Mouse height is the top of the voxel where the mouse is hovering."""
        G = self.grid.xfm_pg(pygame.mouse.get_pos())
        voxels = self.voxel_artwork.layout
        h = 0; z = 0
        if G in voxels:
            h = voxels[G]['height']
            z = voxels[G]['z']
        # Store these values for use elsewhere
        self.mouses['mouse_height'] = h
        self.mouses['mouse_z'] = z

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
        pygame.draw.polygon(self.surfs['surf_game_art'], Color(100,255,100), points, width=5)

    def render_grid_tile_highlighted_at_mouse_around_player(self) -> None:
        """Render just the front of the highlight around the player when mouse is on player's tile."""
        G = self.grid.xfm_pg(pygame.mouse.get_pos())
        Gs = [ # Define only the front part of the square tile on the grid
                (G[0]  ,G[1]  ),
                (G[0]+1,G[1]  ),
                (G[0]+1,G[1]+1)]
        points = [self.grid.xfm_gp(G) for G in Gs]
        pygame.draw.lines(self.surfs['surf_game_art'], Color(100,255,100), False, points, width=5)

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

