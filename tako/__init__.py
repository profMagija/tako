
import astma
import astma.mods
from astma import ansi

from mako.desktop.MakoDesktopDatabase import MakoDesktopDatabase
from mako.lib import schedule

import os
import itertools
from datetime import datetime

_OPTIONS = {
    'show_inactive_tasks': False
}

_COLLAPSED = set()

def _bool_parser(text):
    orig = text
    text = text.lower()

    if text in ['y', 'yes', 'true', 'on', '1', 'oui', 'teraj']:
        return True
    
    if text in ['n', 'no', 'false', 'off', '0', 'non', 'nemere']:
        return False

    raise ValueError("invalid boolean value: '{}'".format(orig))

def _due_parser(due):
    if due == "current":
        due = datetime(datetime.now().year, datetime.now().month, 28)
    else:
        due = datetime.strptime(due, "%Y-%m-%d")
    return due

mdb = MakoDesktopDatabase(path='{}/.mako/db'.format(os.environ["HOME"]))

ui = astma.mods.statusline(astma.mods.mod())

def set_view(mod):
    ui.child = mod
    if hasattr(ui, 'buf'):
        ui.set_buf(ui.buf)
        ui.redraw()

@ui.ask_param('name', 'Task name')
@ui.ask_param('expected', 'Expected time', convertor=int)
@ui.ask_param('spent', 'Time spent', default=0, convertor=int)
@ui.ask_param('done', 'Done', default=False, convertor=_bool_parser)
@ui.ask_param('due', 'Due date', default_in='current', convertor=_due_parser)
def create_new_task(subproj, 
        name=None,
        expected=None,
        spent=None,
        done=None,
        due=None):
    # TODO: check this BEFORE asking for subproject name ...
    if not isinstance(subproj, schedule.ScheduleSubproject):
        ui.left_text = ' Must select a subproject!'
        return


    subproj.addTask(schedule.Task(name, expected, spent=spent, done=done, due=due))
    save_changes()
    update_project_list()

@ui.ask_param('name', 'Subproject name')
def create_new_subproject(proj, name=None):
    # TODO: check this BEFORE asking for subproject name ...
    if not isinstance(proj, schedule.ScheduleProject):
        ui.left_text = ' Must select a project!'
        return
    proj.addSubproject(schedule.ScheduleSubproject(name))
    save_changes()
    update_project_list()

@ui.ask_param('name', 'Project name')
def create_new_project(name=None):
    _PROJS.append(schedule.ScheduleProject(name, (255, 0, 0), (255, 255, 255)))
    save_changes()
    update_project_list()

@ui.ask_param('new_name', 'New name')
def rename_thing(thing, new_name=None):
    if isinstance(thing, schedule.Task):
        thing.text = new_name
    else:
        thing.name = new_name

    save_changes()
    update_project_list()

def make_items_from_projs(projs):
    l = []
    _show_all_tasks = _OPTIONS['show_inactive_tasks']

    for p in projs:
        l.append(p)
        if p in _COLLAPSED:
            continue
        for subproj in p.subprojects:
            l.append(subproj)
            if subproj in _COLLAPSED:
                continue
            for task in subproj.tasks:
                if _show_all_tasks or not task.isDone():
                    l.append(task)

    return l

def toggle_collapse(item):
    if item is None:
        if not _COLLAPSED:
            for p in _PROJS:
                _COLLAPSED.add(p)
                for sp in p.subprojects:
                    _COLLAPSED.add(sp)
        else:
            _COLLAPSED.clear()
    elif item in _COLLAPSED:
        _COLLAPSED.remove(item)
    else:
        _COLLAPSED.add(item)

    update_project_list()

def toggle_inactive_tasks():
    _OPTIONS['show_inactive_tasks'] = not _OPTIONS['show_inactive_tasks']
    update_project_list()

_PICKER = None
_KB = None
_PROJS = None

def formatter(item):
    collapsed = ' …' if item in _COLLAPSED else ''
    if isinstance(item, schedule.ScheduleProject):
        return item.name + collapsed
    if isinstance(item, schedule.ScheduleSubproject):
        return ' └ ' + item.name + collapsed
    if isinstance(item, schedule.Task):
        done_str = ''
        if _OPTIONS['show_inactive_tasks']:
            done_str = '[{}] '.format('x' if item.done else ' ')
        
        return '   └ {}{:20} [{:3} / {:3}] [{}]'.format(done_str, item.text, item.spent, item.expected, str(item.due))
        
    return repr(item) + ' ?? '
    
def mark_done(item):
    if not isinstance(item, schedule.Task):
        return

    item.done = not item.isDone()

    save_changes()
    update_project_list()

def init_project_list():
    global _PICKER, _KB, _PROJS

    projs = mdb.downloadProjects()
    items = make_items_from_projs(projs)
    lst = astma.mods.picker(items, 
        print_function=formatter,
        selected_color=ansi.RESET + ansi.CYAN_FG)
    kb = astma.mods.keybind(lst, keybinds={
        'p': lambda: create_new_project(projs),
        's': lambda: create_new_subproject(lst.items[lst.index]),
        't': lambda: create_new_task(lst.items[lst.index]),
        'r': lambda: rename_thing(lst.items[lst.index]),
        'd': lambda: mark_done(lst.items[lst.index]),
        'z': {
            'a': lambda: toggle_collapse(lst.items[lst.index]),
            'A': lambda: toggle_collapse(None),
            'z': lambda: toggle_inactive_tasks()
        }
    })
    _PICKER, _KB, _PROJS = lst, kb, projs
    set_view(kb)

def save_changes():
    mdb.uploadProjects(_PROJS)

def update_project_list():
    _PICKER.items = make_items_from_projs(_PROJS)
    _PICKER.index = min(_PICKER.index, len(_PICKER.items) - 1)
    _PICKER.redraw()

def show_schedule():
    s = mdb.downloadSchedules()[-1]
    tbl = astma.mods.table(cols=8, 
        has_title=True,
        selectable=True, 
        select_color=ansi.WHITE_BG + ansi.BLACK_FG)
    tbl.insert_row(['Time', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
    
    entries = {(e.day, e.start): e for e in s.getEntries()}

    for hour in range(24):
        l = ['{:02}:00'.format(hour)]
        for day in range(1, 8):
            if (day, hour) in entries:
                e = entries[day, hour]
                l.append('{} - {}'.format(e.project, e.subproject))
            else:
                l.append('')

        tbl.insert_row(l)

    set_view(tbl)

def run():
    init_project_list()
    astma.app.run_app(ui)

