# This file is part of Checkbox.
#
# Copyright 2017 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`checkbox_ng.urwid_ui` -- user interface URWID elements
============================================================
"""

from gettext import gettext as _
import urwid


_widget_cache = {}
test_info_list = ()
show_job_ids = False


class FlagUnitWidget(urwid.TreeWidget):
    # apply an attribute to the expand/unexpand icons
    unexpanded_icon = urwid.AttrMap(
        urwid.TreeWidget.unexpanded_icon, 'dirmark')
    expanded_icon = urwid.AttrMap(
        urwid.TreeWidget.expanded_icon, 'dirmark')
    selected = urwid.Text(u'[X]')
    unselected = urwid.Text(u'[ ]')

    def __init__(self, node):
        self.flagged = True
        super().__init__(node)
        # insert an extra AttrWrap for our own use
        self._w = urwid.AttrWrap(self._w, None)
        self.update_w()

    def selectable(self):
        return True

    def get_indented_widget(self):
        indent_cols = self.get_indent_cols()
        widget = self.get_inner_widget()
        if self.is_leaf:
            widget = urwid.Columns(
                [(3, [self.selected, self.unselected][self.flagged]),
                 urwid.Padding(widget,
                               width=('relative', 100),
                               left=indent_cols)],
                dividechars=1)
        else:
            widget = urwid.Columns(
                [(3, [self.selected, self.unselected][self.flagged]),
                 (indent_cols-1, urwid.Text(' ')),
                 (1, [self.unexpanded_icon,
                      self.expanded_icon][self.expanded]),
                 urwid.Padding(widget, width=('relative', 100))],
                dividechars=1)
        return widget

    def update_expanded_icon(self):
        """Update display widget text for parent widgets"""
        # icon is second element in columns indented widget
        self._w.base_widget.widget_list[2] = [
            self.unexpanded_icon, self.expanded_icon][self.expanded]

    def keypress(self, size, key):
        key = super().keypress(size, key)
        if key:
            key = self.unhandled_keys(size, key)
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        if self.is_leaf or event != 'mouse press' or button != 1:
            return False
        if row == 0 and col == self.get_indent_cols() + 4:
            self.expanded = not self.expanded
            self.update_expanded_icon()
            return True
        return False

    def unhandled_keys(self, size, key):
        if key == " ":
            self.flagged = not self.flagged
            self.set_descendants_state(self.flagged)
            self.set_ancestors_state(self.flagged)
            self.update_w()
        elif not self.is_leaf and key == "enter":
            self.expanded = not self.expanded
            self.update_expanded_icon()
        elif key in ('i', 'I'):
            global show_job_ids, _widget_cache
            show_job_ids = not show_job_ids
            for w in _widget_cache.values():
                w._w.base_widget.widget_list[-1] = urwid.Padding(
                    w.load_inner_widget(),
                    width=('relative', 100),
                    left=w.get_indent_cols())
        else:
            return key

    def set_ancestors_state(self, new_state):
        """Set the selection state of all ancestors consistently."""
        parent = self.get_node().get_parent()
        # If child is set, then all ancestors must be set
        if self.flagged:
            while parent:
                parent_w = parent.get_widget()
                parent_w.flagged = new_state
                parent_w.update_w()
                parent = parent.get_parent()
        # If child is not set, then all ancestors mustn't be set
        # unless another child of the ancestor is set
        else:
            while parent:
                if any((parent.get_child_node(key).get_widget().flagged
                        for key in parent.get_child_keys())):
                    break
                parent_w = parent.get_widget()
                parent_w.flagged = new_state
                parent_w.update_w()
                parent = parent.get_parent()

    def set_descendants_state(self, new_state):
        """Set the selection state of all descendants recursively."""
        if self.is_leaf:
            return
        node = self.get_node()
        for key in node.get_child_keys():
            child_w = node.get_child_node(key).get_widget()
            child_w.flagged = new_state
            try:
                child_w.update_w()
            except AttributeError:
                break
            child_w.set_descendants_state(new_state)

    def update_w(self):
        """Update the attributes of self.widget based on self.flagged."""
        self._w.attr = 'body'
        self._w.focus_attr = 'focus'
        self._w.base_widget.widget_list[0] = [
            self.unselected, self.selected][self.flagged]


class JobTreeWidget(FlagUnitWidget):
    """Widget for individual files."""
    def __init__(self, node):
        super().__init__(node)
        add_widget(node.get_key(), self)

    def get_display_text(self):
        global show_job_ids
        if show_job_ids:
            return self.get_node().get_key()
        else:
            return self.get_node().get_value()


class CategoryWidget(FlagUnitWidget):
    """Widget for a category."""
    def __init__(self, node):
        super().__init__(node)
        self.expanded = False
        if node.get_depth() == 0:
            self.expanded = True
        self.update_expanded_icon()

    def get_display_text(self):
        node = self.get_node()
        if node.get_depth() == 0:
            return _("Categories")
        else:
            return node.get_value().get_category(node.get_key()).tr_name()


class JobNode(urwid.TreeNode):
    """Metadata storage for individual jobs"""

    def load_widget(self):
        return JobTreeWidget(self)


class CategoryNode(urwid.ParentNode):
    """Metadata storage for categories"""

    def load_widget(self):
        return CategoryWidget(self)

    def load_child_keys(self):
        if self.get_depth() == 0:
            return sorted(
                self.get_value().get_participating_categories(),
                key=lambda c: self.get_value().get_category(c).tr_name())
        else:
            return sorted([
                job['id'] for job in test_info_list
                if job['category_id'] == self.get_key()])

    def load_child_node(self, key):
        """Return either a CategoryNode or JobNode"""
        if self.get_depth() == 0:
            return CategoryNode(self.get_value(), parent=self,
                                key=key, depth=self.get_depth() + 1)
        else:
            value = next(
                job['name'] for job in test_info_list if job.get("id") == key)
            return JobNode(
                value, parent=self, key=key, depth=self.get_depth() + 1)


class CategoryBrowser:
    palette = [
        ('body', 'light gray', 'black'),
        ('focus', 'black', 'light gray', 'standout'),
        ('head', 'black', 'light gray', 'standout'),
        ('foot', 'light gray', 'black'),
        ('title', 'white', 'black', 'bold'),
        ('dirmark', 'light gray', 'black', 'bold'),
        ('start', 'dark green,bold', 'black'),
        ('rerun', 'yellow,bold', 'black'),
        ]

    footer_text = [('Press ('), ('start', 'T'), (') to start Testing')]

    def __init__(self, title, sa):
        job_units = [sa.get_job(job_id) for job_id in
                     sa.get_static_todo_list()]
        global test_info_list
        test_info_list = tuple(({
            "id": job.id,
            "name": job.tr_summary(),
            "category_id": sa.get_job_state(job.id).effective_category_id,
        } for job in job_units))
        self.header = urwid.Padding(urwid.Text(title), left=1)
        root_node = CategoryNode(sa)
        root_node.get_widget().set_descendants_state(True)
        self.listbox = urwid.TreeListBox(urwid.TreeWalker(root_node))
        self.listbox.offset_rows = 1
        self.footer = urwid.Padding(urwid.Text(self.footer_text), left=1)
        self.view = urwid.Frame(
            urwid.AttrWrap(urwid.LineBox(self.listbox), 'body'),
            header=urwid.AttrWrap(self.header, 'head'),
            footer=urwid.AttrWrap(self.footer, 'foot'))

    def run(self):
        """Run the urwid MainLoop."""
        self.loop = urwid.MainLoop(
            self.view, self.palette, unhandled_input=self.unhandled_input)
        self.loop.run()
        selection = []
        global test_info_list, _widget_cache
        for w in _widget_cache.values():
            if w.flagged:
                selection.append(w.get_node().get_key())
        _widget_cache = {}
        test_info_list = ()
        return frozenset(selection)

    def unhandled_input(self, key):
        if key in ('t', 'T'):
            raise urwid.ExitMainLoop()

def TestPlanBrowser(title, test_plan_list, selection=None):
    palette = [
        ('body', 'light gray', 'black', 'standout'),
        ('header', 'black', 'light gray', 'bold'),
        ('buttnf', 'black', 'light gray'),
        ('buttn', 'light gray', 'black', 'bold'),
        ('foot', 'light gray', 'black'),
        ('start', 'dark green,bold', 'black'),
        ]
    footer_text = [('Press '), ('start', '<Enter>'), (' to continue')]
    radio_button_group = []
    blank = urwid.Divider()
    listbox_content = [
        blank,
        urwid.Padding(urwid.Pile(
            [urwid.AttrWrap(urwid.RadioButton(
                radio_button_group,
                txt, state=False), 'buttn', 'buttnf')
                for txt in test_plan_list]),
            left=4, right=3, min_width=13),
        blank,
        ]
    if selection:
        radio_button_group[selection].set_state(True)
    header = urwid.AttrWrap(urwid.Padding(urwid.Text(title), left=1), 'header')
    footer = urwid.AttrWrap(
        urwid.Padding(urwid.Text(footer_text), left=1), 'foot')
    listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
    frame = urwid.Frame(urwid.AttrWrap(urwid.LineBox(listbox), 'body'),
                        header=header, footer=footer)
    del frame._command_map["enter"]

    def unhandled(key):
        if key == "enter":
            raise urwid.ExitMainLoop()

    urwid.MainLoop(frame, palette, unhandled_input=unhandled).run()
    try:
        return next(
            radio_button_group.index(i) for i in radio_button_group if i.state)
    except StopIteration:
        return None


def add_widget(id, widget):
    """Add the widget for a given id."""
    _widget_cache[id] = widget
