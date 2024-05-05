#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Utilities
"""

import sys
import logging
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

class OsWindow:
    """OS window information.

    size -- (w,h) - sets initial window size and tracks value when window is resized.
    flags -- OR'd bitflags for window behavior. Default is pygame.RESIZABLE.
    """
    def __init__(self, size:tuple, flags:int=pygame.RESIZABLE):
        self.size = size
        self.flags = flags

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

class DebugHud:
    def __init__(self, game):
        self.game = game
        self.debug_text = ""
        self.is_visible = True

    def clear_text(self) -> None:
        self.debug_text = ""

    def add_text(self, debug_text:str):
        """Add another line of debug text.

        :param debug_text:str -- add this string to the HUD

        Debug text always has FPS and Mouse.
        Each call to add_text() adds a line below that.
        """
        self.debug_text += f"\n{debug_text}"

    def render(self, color:Color = Color(255,255,255)):
        # self.text = Text((0,0), font_size=36, sys_font="Built-in Pygame Font")
        self.text = Text((0,0), font_size=15, sys_font="Roboto Mono")
        mpos = pygame.mouse.get_pos()
        self.text.update(f"FPS: {self.game.clock.get_fps():0.1f} | Mouse: {mpos}"
                         f"{self.debug_text}")
        self.text.render(self.game.surfs['surf_os_window'], color)
