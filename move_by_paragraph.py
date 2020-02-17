from __future__ import print_function
import sublime
from sublime import Region
from sublime_plugin import TextCommand
from collections import Iterable



DEBUG = False

def dbg(*msg):
    if DEBUG:
        print(' '.join(map(str, msg)))


SETTINGS_FILE = "MoveByParagraph.sublime-settings"

class MyCommand(TextCommand):

    def set_cursor_to(self, pos):
        """ Sets the cursor to a given position. If multiple
        positions are given, a multicursor will be made.
        """
        dbg('setting cursor to {0}'.format(pos))
        if not isinstance(pos, Iterable):
            pos = [pos]
        self.view.sel().clear()
        for p in pos:
            self.view.sel().add(Region(p, p))

    def set_selection_to(self, start, end):
        dbg("setting selection to {0}".format((start, end)))
        self.view.sel().clear()
        self.view.sel().add(Region(start, end))

    def get_char_at(self, pos):
        """ Return the character at a position """
        return self.view.substr(Region(pos, pos + 1))

    def get_current_line(self):
        """ Return the line at the current cursor """
        return self.get_line_at(self.get_cursor())

    def get_line_at(self, region):
        """ Returns the :class:`sublime.Line` at a
        :class:`sublime.Region`
        """
        return self.view.line(region)

    def get_cursor(self):
        """ Returns the first current cursor """
        return self.view.sel()[0]


class MoveByParagraphCommand(MyCommand):

    def __init__(self, view):
        super(MoveByParagraphCommand, self).__init__(view)
        self.settings = sublime.load_settings(SETTINGS_FILE)

    def _is_empty(self, line):
        s = self.view.substr(line)
        if self.settings.get('ignore_whitespace', False):
            return not s.strip()
        else:
            # Okuno: I'm not sure why the second part of this clause is here
            return not s # and self.view.substr(max(0, line.begin() - 1)) == '\n'

    def _find_paragraph_position_forward(self, start, to_next):
        size = self.view.size()
        r = Region(start, size)
        lines = self.view.split_by_newlines(r)
        # This is a state machine with two states: non-empty and empty.
        # In state non-empty, stay there unless an empty line is found.
        # In state empty, terminate when a non-empty line is found.
        # In either state, terminate at end of file.
        found_empty = False
        for n, line in enumerate(lines):
            s = self.view.substr(line)
            if self._is_empty(line):
                found_empty = True
                if not to_next:
                    # if we started on an empty line, go to next paragraph
                    # regardless of to_next setting
                    if n == 0:
                        to_next = True
                    else:
                        return line
            elif found_empty:
                return line
        else:
            if self.view.substr(Region(size - 1, size)) == '\n':
                # We want to jump to the very end if we reached the file and
                # it ends with a newline.  If the file ends with a newline,
                # the lines array does not end with u'' as expected, which is
                # why we need to do this
                return Region(size, size)
            else:
                return lines[-1]

    def _find_paragraph_position_backward(self, start, to_next):
        r = Region(0, start)
        lines = self.view.split_by_newlines(r)
        # This state machine has three states: unknown, skip empty, and skip
        # non-empty (full). It starts in unknown, but moves to skip
        # {empty,non-empty} if the next line is {empty,non-empty} respectively.
        # It then skips lines until it finds one of the opposite type. here, the
        # behavior is dirven by the no_next argument:
        #  * If we were skipping blank lines, we've only found the end of the
        #    prior paragraph, so if to_next is /not/ set, we should go to
        #    skipping full lines.
        #  * If we were skipping full lines, we've just found the start of the
        #    current paragraph, so if to_next is set, we should go to skipping
        #    blank lines.
        # That said, it makes a lot more sense to draw out the state transition
        # diagram and run it manually on some text.
        skip_empty, skip_full = False, False
        for n in range(len(lines) - 1, 0, -1):
            line = lines[n-1]
            if skip_empty:
                if not self._is_empty(line):
                    if to_next:
                        return lines[n]
                    else:
                        skip_empty, skip_full = False, True
            elif skip_full:
                if self._is_empty(line):
                    if to_next:
                        skip_empty, skip_full = True, False
                    else:
                        return lines[n]
            else:
                if self._is_empty(line):
                    skip_empty = True
                else:
                    skip_full = True
        else:
            return lines[0]

    def find_paragraph_position(self, start, *, forward, to_next):
        dbg('Starting from {0}'.format(start))
        if forward:
            return self._find_paragraph_position_forward(start, to_next)
        else:
            return self._find_paragraph_position_backward(start, to_next)

    def run(self, edit, extend=False, forward=False, to_next=None):
        """
        The cursor will move to beginning of a non-empty line that succeeds
        an empty one.  Selection is supported when "extend" is True.
        """
        # Default is to go to start of next paragraph when moving forward,
        # but only to start of this paragraph when moving backward.
        if to_next is None:
            to_next = forward

        cursor = self.get_cursor()
        if cursor.a < cursor.b:
            start = cursor.end()
        else:
            start = cursor.begin()
        line = self.find_paragraph_position(start,
            forward=forward,
            to_next=to_next)
        dbg('Stopping at {0}'.format(self.view.substr(line)))

        if extend:
            self.set_selection_to(cursor.a, line.begin())
        else:
            self.set_cursor_to(line.begin())
        cursor = self.get_cursor()
        self.view.show(cursor)
