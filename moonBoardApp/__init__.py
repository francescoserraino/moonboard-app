# -*- coding: utf-8 -*-
# moonboard-app/__init__.py

from moonboard_problems import HOLDS_CONF, _new_site_problems_ids_and_author, load_problems, get_setups, problems_data
from draw_problem import draw_Problem,background_image_path
from drive_moonboard_LEDS import init_pixels, test_leds, show_problem, clear_problem
from  assets import bundles

from flask import Flask,request,redirect,render_template,url_for
from flask_socketio import SocketIO
from flask_assets import Environment
#from flask_jsglue import JSGlue
import eventlet
eventlet.monkey_patch()

import json
import sched
from pathlib import Path
from PIL.ImageColor import colormap,getrgb

###############
###############
# GLOBALS
#paths
APP_ROOT = Path(__file__).parent.relative_to(Path().absolute())
STATIC_FILE_PATH = APP_ROOT.joinpath('static')
IMAGE_FOLDER_PATH  = STATIC_FILE_PATH.joinpath("img")
PROBLEMS_DIR_PATH = APP_ROOT.joinpath('problems')
PROBLEM_IMAGE_PATH = IMAGE_FOLDER_PATH.joinpath('current_problem.png')
FAVORITES_PATH = APP_ROOT.joinpath('favorites').joinpath('contest.json')

#problems
LED_BRIGHTNESS_LEVELS={"Low":80,"Medium":100,"High":150}
LED_BRIGHTNESS = "Medium"

HOLD_COLORS = {
    'SH': getrgb(colormap["blueviolet"]),
    'IH': getrgb(colormap["darkgreen"]),
    'FH': getrgb(colormap["red"])
}

#init led hardware and turn led off
MOONBOARD_PIXELS = init_pixels(type='raspberry')

CURRENT_HOLD_SETUP_KEY= 1 #A+B+OS 2016

PROBLEMS = load_problems(PROBLEMS_DIR_PATH)
PROBLEMS_DATA, PROBLEMS_DATA_BY_HOLDS = problems_data(CURRENT_HOLD_SETUP_KEY,PROBLEMS)

SELECTED_PROBLEM_KEY = None

def init_problems_var(clear=False):
    global SELECTED_PROBLEM_KEY, PROBLEMS, PROBLEMS_BY_HOLDS
    SELECTED_PROBLEM_KEY = None
    #turn off leds
    if clear:
        clear_problem(MOONBOARD_PIXELS)
    #draw empty problem
    draw_Problem({},
                 background_image_path(IMAGE_FOLDER_PATH, CURRENT_HOLD_SETUP_KEY),
                 PROBLEM_IMAGE_PATH,
                 HOLD_COLORS)

    print("Number of problems founds: {}.".format(len(PROBLEMS)))
    print("Setups founds:")
    print get_setups(PROBLEMS)

#FAvorites
FAVORITES = set()

def load_favorites(path=None):
    global FAVORITES
    if path is not None:
        file_content = json.load(open(path, 'r+'))
        favorites = list(file_content.keys())
    else:
        favorites = list()
    FAVORITES = set(favorites)

load_favorites()
init_problems_var(clear=True)

####################
app = Flask(__name__)
app.debug=True
socket = SocketIO(app)
assets = Environment(app)
assets.register(bundles)
#jsglue = JSGlue(app)

@app.route('/')
def index():
    return redirect(url_for('problems_table'))

@app.route('/problems_table')
def problems_table():
    init_problems_var()
    columns = ['name', 'grade', 'author','favorite']
    grades_list =sorted(list({v['grade'] for k, v in PROBLEMS.items()}))
    return render_template('problems_table.html', columns = columns, grades=grades_list)

@app.route('/_get_problems')
def get_problems_data():
    favorites = (request.args.get('favorites')=='True')
    #favorites
    for r in PROBLEMS_DATA:
        r['favorite'] = r['id'] in FAVORITES

    if favorites :
        return json.dumps({"data":[r for r in PROBLEMS_DATA if r['favorite']]})
    else:
        return json.dumps({"data":PROBLEMS_DATA})

# @app.route('/_get_problems_by_holds',methods=['POST','GET'])
# def get_problems_by_holds():
#     holds = request.form['holds']
#     holds = holds.replace(';',',').split(',')
#     print(holds)
#     matching_problems = set.intersection(*[PROBLEMS_DATA_BY_HOLDS.get(h.strip(),set([])) for h in holds])
#     data = [r for r in PROBLEMS_DATA if r['id'] in matching_problems]
#     for r in data:
#         r['favorite'] = r['id'] in FAVORITES
#     return json.dumps({"data":data})

@app.route('/_select_problem', methods=['POST'])
def select_problem():
    global SELECTED_PROBLEM_KEY
    problem_id = request.form['problem_id']
    if problem_id=="":
        print(" No selected problem.")
        SELECTED_PROBLEM_KEY = None
        draw_Problem({},
                     background_image_path(IMAGE_FOLDER_PATH, CURRENT_HOLD_SETUP_KEY),
                     PROBLEM_IMAGE_PATH,
                     HOLD_COLORS)
        clear_problem(MOONBOARD_PIXELS)
    else:
        print("Selected problem ID: {}".format(problem_id))
        SELECTED_PROBLEM_KEY = problem_id
        holds = PROBLEMS.get(SELECTED_PROBLEM_KEY, {}).get('holds', {})
        draw_Problem(PROBLEMS.get(SELECTED_PROBLEM_KEY, {}),
                     background_image_path(IMAGE_FOLDER_PATH, CURRENT_HOLD_SETUP_KEY),
                     PROBLEM_IMAGE_PATH,
                     HOLD_COLORS)
        show_problem(MOONBOARD_PIXELS, holds, HOLD_COLORS, brightness=LED_BRIGHTNESS_LEVELS[LED_BRIGHTNESS])
    return "OK"

@app.route('/_set_as_favorites', methods=['POST'])
def set_as_favorites():
    global FAVORITES, SELECTED_PROBLEM_KEY
    problem_id = request.form['problem_id']
    action = request.form['action']
    if action=="add":
        print("Add problem {} to favorites".format(problem_id))
        FAVORITES.add(problem_id)
    elif action=='rm':
        print("Remove problem {} from favorites".format(problem_id))
        FAVORITES.remove(problem_id)
        if SELECTED_PROBLEM_KEY==problem_id:
            SELECTED_PROBLEM_KEY = None
            draw_Problem({},
                         background_image_path(IMAGE_FOLDER_PATH, CURRENT_HOLD_SETUP_KEY),
                         PROBLEM_IMAGE_PATH,
                         HOLD_COLORS)
            clear_problem(MOONBOARD_PIXELS)
        return "SELECTED"
    elif action=='rmall':
        print("Remove all problems from favorites")
        FAVORITES = set()

    return "OK"

@app.route('/_export_favorites', methods=['POST'])
def export_favorites():
    favorites = {}
    key = ["name", "author", "grade","site_id"]

    for r in PROBLEMS_DATA:
        if r['favorite']:
            favorites[r['site_id']]={k:v for k,v in r.items() if k in key}

    with open(str(FAVORITES_PATH),'w+') as output:
        # Pickle dictionary using protocol 0.
        json.dump(favorites,output)

    return "OK"

@app.route('/favorites_table')
def favorites_table():
    init_problems_var()
    if (request.args.get('file') == 'contest'):
        path=str(FAVORITES_PATH)
        load_favorites(path)
    columns = ["",'name', 'grade', 'author']
    return render_template('favorites_table.html',columns = columns)

@app.route('/search_by_holds')
def search_by_holds():
    init_problems_var()
    columns = ['name', 'grade', 'author','favorite']
    return render_template('search_by_holds.html', columns = columns)

############
#settings
@app.route('/settings')
def settings():
    clear_problem(MOONBOARD_PIXELS)
    setup = {k:{ 'name':", ".join(list(v)), 'selected': k == CURRENT_HOLD_SETUP_KEY} \
                      for k,v in HOLDS_CONF["setup"].items()}
    return render_template("settings.html", holds_setup= setup, brightness_levels=LED_BRIGHTNESS_LEVELS, brightness=LED_BRIGHTNESS)

@app.route('/_set_holds_setup', methods=['POST'])
def _set_hold_combination():
    global CURRENT_HOLD_SETUP_KEY, PROBLEMS_DATA, PROBLEMS_DATA_BY_HOLDS
    CURRENT_HOLD_SETUP_KEY = int(request.form.get('holds_setup_k'))
    PROBLEMS_DATA, PROBLEMS_DATA_BY_HOLDS = problems_data(CURRENT_HOLD_SETUP_KEY, PROBLEMS)
    print  "Change hold setup to {}:{}.".format(CURRENT_HOLD_SETUP_KEY,HOLDS_CONF['setup'][CURRENT_HOLD_SETUP_KEY])
    return "OK"

@app.route('/_set_led_brightness',  methods=['POST'])
def _set_led_brightness():
    global LED_BRIGHTNESS
    LED_BRIGHTNESS = request.form.get('brightness')
    print(LED_BRIGHTNESS_LEVELS[LED_BRIGHTNESS])
    return "OK"


# def fetch_problems(delay):
#     i = delay
#     while True:
#
#         if i<1:
#             print("fetch led problems")
#             i=delay
#         else:
#             i -= 1
#             eventlet.sleep(1)
#
#
# #eventlet.spawn(fetch_problems, delay = 5.0)