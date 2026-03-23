from PySide6.QtGui import QUndoCommand

class BaseCommand(QUndoCommand):
    def __init__(self, description, main_window):
        super().__init__(description)
        self.main_window = main_window

    def refresh(self):
        if self.main_window:
            self.main_window.full_refresh()

class ProjectSettingsCommand(BaseCommand):
    def __init__(self, project, attr_name, old_val, new_val, description, main_window):
        super().__init__(description, main_window)
        self.project = project
        self.attr_name = attr_name
        self.old_val = old_val
        self.new_val = new_val

    def redo(self):
        setattr(self.project, self.attr_name, self.new_val)
        self.refresh()

    def undo(self):
        setattr(self.project, self.attr_name, self.old_val)
        self.refresh()

class PropertyChangeCommand(BaseCommand):
    def __init__(self, obj, attr_name, old_val, new_val, description, main_window):
        super().__init__(description, main_window)
        self.obj = obj
        self.attr_name = attr_name
        self.old_val = old_val
        self.new_val = new_val

    def redo(self):
        setattr(self.obj, self.attr_name, self.new_val)
        self.refresh()

    def undo(self):
        setattr(self.obj, self.attr_name, self.old_val)
        self.refresh()

class ListPropertyChangeCommand(BaseCommand):
    def __init__(self, lst, index, old_val, new_val, description, main_window):
        super().__init__(description, main_window)
        self.lst = lst
        self.index = index
        self.old_val = old_val
        self.new_val = new_val

    def redo(self):
        self.lst[self.index] = self.new_val
        self.refresh()

    def undo(self):
        self.lst[self.index] = self.old_val
        self.refresh()

class SetPropertyCommand(BaseCommand):
    def __init__(self, obj, attr_name, method_add, method_remove, item, description, main_window):
        super().__init__(description, main_window)
        self.obj = obj
        self.attr_name = attr_name
        self.method_add = method_add
        self.method_remove = method_remove
        self.item = item

    def redo(self):
        getattr(self.obj, self.method_add)(self.item)
        self.refresh()

    def undo(self):
        getattr(self.obj, self.method_remove)(self.item)
        self.refresh()
class AddItemCommand(BaseCommand):
    def __init__(self, lst, item, description, main_window, sort_callback=None):
        super().__init__(description, main_window)
        self.lst = lst
        self.item = item
        self.sort_callback = sort_callback

    def redo(self):
        self.lst.append(self.item)
        if self.sort_callback:
            self.sort_callback()
        self.refresh()

    def undo(self):
        self.lst.remove(self.item)
        if self.sort_callback:
            self.sort_callback()
        self.refresh()

class InsertItemCommand(BaseCommand):
    def __init__(self, lst, index, item, description, main_window):
        super().__init__(description, main_window)
        self.lst = lst
        self.index = index
        self.item = item

    def redo(self):
        self.lst.insert(self.index, self.item)
        self.refresh()

    def undo(self):
        self.lst.pop(self.index)
        self.refresh()

class RemoveItemCommand(BaseCommand):
    def __init__(self, lst, index, item, description, main_window):
        super().__init__(description, main_window)
        self.lst = lst
        self.index = index
        self.item = item

    def redo(self):
        self.lst.pop(self.index)
        self.refresh()

    def undo(self):
        self.lst.insert(self.index, self.item)
        self.refresh()

class ReplaceItemCommand(BaseCommand):
    def __init__(self, lst, index, old_item, new_item, description, main_window):
        super().__init__(description, main_window)
        self.lst = lst
        self.index = index
        self.old_item = old_item
        self.new_item = new_item

    def redo(self):
        self.lst[self.index] = self.new_item
        self.refresh()

    def undo(self):
        self.lst[self.index] = self.old_item
        self.refresh()

class KeyframeMoveCommand(BaseCommand):
    def __init__(self, keyframe, old_time, old_val, new_time, new_val, description, main_window):
        super().__init__(description, main_window)
        self.keyframe = keyframe
        self.old_time = old_time
        self.old_val = old_val
        self.new_time = new_time
        self.new_val = new_val

    def redo(self):
        self.keyframe.time = self.new_time
        self.keyframe.value = self.new_val
        self.refresh()

    def undo(self):
        self.keyframe.time = self.old_time
        self.keyframe.value = self.old_val
        self.refresh()

class SequenceMoveCommand(BaseCommand):
    def __init__(self, sequence, old_start, new_start, description, main_window):
        super().__init__(description, main_window)
        self.sequence = sequence
        self.old_start = old_start
        self.new_start = new_start

    def redo(self):
        self.sequence.start_time = self.new_start
        self.refresh()

    def undo(self):
        self.sequence.start_time = self.old_start
        self.refresh()

class SequenceResizeCommand(BaseCommand):
    def __init__(self, sequence, old_start, old_dur, old_offset, new_start, new_dur, new_offset, description, main_window):
        super().__init__(description, main_window)
        self.sequence = sequence
        self.old_start = old_start
        self.old_dur = old_dur
        self.old_offset = old_offset
        self.new_start = new_start
        self.new_dur = new_dur
        self.new_offset = new_offset

    def redo(self):
        self.sequence.start_time = self.new_start
        self.sequence.duration = self.new_dur
        self.sequence.audio_offset = self.new_offset
        self.refresh()

    def undo(self):
        self.sequence.start_time = self.old_start
        self.sequence.duration = self.old_dur
        self.sequence.audio_offset = self.old_offset
        self.refresh()

class BatchCommand(BaseCommand):
    def __init__(self, commands, description, main_window):
        super().__init__(description, main_window)
        self.commands = commands

    def redo(self):
        for cmd in self.commands:
            cmd.redo()
        self.refresh()

    def undo(self):
        for cmd in reversed(self.commands):
            cmd.undo()
        self.refresh()
