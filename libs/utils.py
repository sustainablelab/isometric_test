#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Utilities
"""

import sys
import logging
from pathlib import Path
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color

logger = logging.getLogger(__name__)

def setup_logging(loglevel:str="DEBUG") -> logging.Logger:
    """Set up a logger.

    Setup in main application:

        logger = setup_logging()

    Setup in library code:

        from libs.utils import setup_logging
        if __name__ == '__main__':
            logger = logging.getLogger(__name__)

    Usage example 1: Debug a variable

        a = 1
        logger.debug(f"a: {a}")

    Usage example 2: Exit due to an error

        match a:
            case 1:
                pass
            case _:
                logger.error(f"Unexpected value of a: {a}")
                sys.exit("Exit due to error. See above.")
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    fmt = '%(asctime)s %(levelname)s in \"%(funcName)s()\" at %(filename)s:%(lineno)d\n\t%(message)s'
    formatter = logging.Formatter(fmt, datefmt='%H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(loglevel)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

def load_image(image_file:Path) -> pygame.Surface:
    """
    image_path: relative to game root folder, type can also be str
    """
    img = pygame.image.load(image_file).convert()
    img.set_colorkey((0,0,0))                           # Treat black as transparent
    return img

class OsWindow:
    """OS window information.

    size -- (w,h) - sets initial window size and tracks value when window is resized.
    flags -- OR'd bitflags for window behavior. Default is pygame.RESIZABLE.
    """
    def __init__(self, size:tuple, is_fullscreen:bool=False):
        # Set initial sizes for windowed and fullscreen
        self._windowed_size = size
        self._fullscreen_size = pygame.display.get_desktop_sizes()[-1]

        # Set initial state: windowed or fullscreen
        self._is_fullscreen = is_fullscreen

        # Update window size and flags to match state of is_fullscreen
        # (size will set to windowed or fullscreen size depending on is_fullscreen)
        # (flags will set to RESIZABLE or FULLSCREEN depending on is_fullscreen)
        self._set_size_and_flags()

    @property
    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    @property
    def size(self) -> tuple:
        return self._size

    @property
    def flags(self) -> tuple:
        return self._flags

    def _set_size_and_flags(self) -> None:
        """Set _size and _flags."""
        if self.is_fullscreen:
            # Update w x h of fullscreen (in case external display changed while game is running).
            # Always use last display listed (if I have an external display, it will list last).
            self._fullscreen_size = pygame.display.get_desktop_sizes()[-1]
            self._size = self._fullscreen_size
            self._flags = pygame.FULLSCREEN
        else:
            self._size = self._windowed_size
            self._flags = pygame.RESIZABLE
        # Report new window size
        logger.debug(f"Window size: {self.size[0]} x {self.size[1]}")

    def toggle_fullscreen(self) -> None:
        """Toggle OS window between full screen and windowed.

        List the sizes of the connected displays:

        ### pygame.display.get_desktop_sizes(): [(2256, 1504), (1920, 1080)]
        logger.debug(f"pygame.display.get_desktop_sizes(): {desktop_sizes}")

        Always use the last size listed:

        ### If my laptop is in Ubuntu Xorg mode and is the only display:
        ###     Fullscreen size: (2256, 1504)
        ### If I connect my Acer monitor:
        ###     Fullscreen size: (1920, 1080)
        logger.debug(f"Fullscreen size: {desktop_sizes[-1]}")
        """
        self._is_fullscreen = not self.is_fullscreen
        logger.debug(f"FULLSCREEN: {self.is_fullscreen}")
        self._set_size_and_flags() # Set size and flags based on fullscreen or windowed

    def handle_WINDOWRESIZED(self, event) -> None:
        """Track size of OS window in self.size"""
        self.size = (event.x, event.y)
        logger.debug(f"Window resized, self.size: {self.size}")

class Text:
    def __init__(self, pos:tuple, font_size:int, sys_font:str):
        self.pos = pos
        self.font_size = font_size
        self.sys_font = sys_font
        self.antialias = True

        if not pygame.font.get_init(): pygame.font.init()

        self.font = pygame.font.SysFont(self.sys_font, self.font_size)

        self.text_lines = []

    def update(self, text:str) -> None:
        """Update text. Split multiline text into a list of lines of text."""
        self.text_lines = text.split("\n")

    def render(self, surf:pygame.Surface, color:Color) -> None:
        """Render text on the surface."""
        for i, line in enumerate(self.text_lines):
            ### render(text, antialias, color, background=None) -> Surface
            text_surf = self.font.render(line, self.antialias, color)
            surf.blit(text_surf,
                      (self.pos[0], self.pos[1] + i*self.font.get_linesize()),
                      special_flags=pygame.BLEND_ALPHA_SDL2
                      )

class HelpHud:
    def __init__(self, game):
        self.game = game
        self.help_text = "HELP\n----"
        self.text = Text((0,0), font_size=15, sys_font="Roboto Mono")

    def add_text(self, help_text:str):
        self.help_text += f"\n{help_text}"

    def render(self, color) -> None:
        self.text.update(f"{self.help_text}")
        self.text.render(self.game.surfs['surf_os_window'], color)

class DebugHud:
    def __init__(self, game):
        self.game = game
        self.debug_text = ""
        # self.text = Text((0,0), font_size=36, sys_font="Built-in Pygame Font")
        self.text = Text((0,0), font_size=15, sys_font="Roboto Mono")

    def add_text(self, debug_text:str):
        """Add another line of debug text.

        :param debug_text:str -- add this string to the HUD

        Debug text always has FPS and Mouse.
        Each call to add_text() adds a line below that.
        """
        self.debug_text += f"\n{debug_text}"

    def render(self, color) -> None:
        mpos = pygame.mouse.get_pos()
        self.text.update(f"FPS: {self.game.clock.get_fps():0.1f} | Mouse: {mpos}"
                         f"{self.debug_text}")
        self.text.render(self.game.surfs['surf_os_window'], color)
