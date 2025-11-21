import cv2 as cv
import pyautogui as pg
import numpy as np
from PIL import ImageGrab
import time
import win32ui, win32gui, win32con, win32api
from stockfish import Stockfish
import random
import sys
from pathlib import Path

def get_screenshot(x1, y1, w, h, windowname = None):
    '''
    takes a screenshot of the screen
    '''
    # get the window image data
    if not windowname:
        hwnd = None
    else:
        hwnd = win32gui.FindWindow(None, windowname)
    
    wDC = win32gui.GetWindowDC(hwnd)
    dcObj = win32ui.CreateDCFromHandle(wDC)
    cDC = dcObj.CreateCompatibleDC()
    dataBitMap = win32ui.CreateBitmap()
    dataBitMap.CreateCompatibleBitmap(dcObj, w, h)
    cDC.SelectObject(dataBitMap)
    cDC.BitBlt((0,0), (w, h), dcObj, (x1, y1), win32con.SRCCOPY)

    # convert the raw data into a format opencv can read
    #dataBitMap.SaveBitmapFile(cDC, 'debug.bmp')
    signedIntsArray = dataBitMap.GetBitmapBits(True)
    img = np.frombuffer(signedIntsArray, dtype='uint8')
    img.shape = (h, w, 4)

    # free resources
    dcObj.DeleteDC()
    cDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, wDC)
    win32gui.DeleteObject(dataBitMap.GetHandle())

    # drop the alpha channel, or cv.matchTemplate() will throw an error like:
    #   error: (-215:Assertion failed) (depth == CV_8U || depth == CV_32F) && type == _templ.type() 
    #   && _img.dims() <= 2 in function 'cv::matchTemplate'
    img = cv.cvtColor(img, cv.COLOR_RGBA2RGB)

    return img

def find_pieces(piece_path, white: bool):
    '''
    returns 'board coords' like a1, a4 in integer format: ie a1 would be (0,0), a4 would be (0,3)
    '''
    piece = cv.imread(piece_path, cv.COLOR_RGBA2RGB)
    res = cv.matchTemplate(piece, screenshot, cv.TM_CCOEFF_NORMED)
    threshold = 0.9
    locations = np.where(res >= threshold)
    locations = list(zip(*locations[::-1]))
    
    rectangles = []
    for loc in locations:
        rect = [int(loc[0]), int(loc[1]), piece.shape[1], piece.shape[0]]
        # Add every box to the list twice in order to retain single (non-overlapping) boxes
        rectangles.append(rect)
        rectangles.append(rect)
        
    rectangles, _ = cv.groupRectangles(rectangles, groupThreshold=1, eps=0.5)

    points = []
    if len(rectangles):
        for (x, y, w, h) in rectangles:
            center_x = x + int(w/2)
            center_y = y + int(h/2)

            points.append((center_x, center_y))
    
    coords = []
    if white:
        for (x, y) in points:
            #0-indexed
            letter = x // 75
            number = 8 - y // 75
            coord = (letter, number)
            coords.append(coord)
    else:
        for (x, y) in points:
            letter = 7 - x // 75
            number = y // 75 - 1
            coord = (letter, number)
            coords.append(coord)
    
    return coords

def make_fen():
    '''
    makes fen code and returns it
    '''
    for path in piece_paths:
        piece_locations.append(find_pieces(path, is_white))
    
    #8 - first stuff before / and letter shows position in slash
    #7 - second stuf before / and letter shows position in slash
    
    piece_order = ['b','k','n','p','q','r','B','K','N','P','Q','R']
    fen_list = [
        [None,None,None,None,None,None,None,None],
        [None,None,None,None,None,None,None,None],
        [None,None,None,None,None,None,None,None],
        [None,None,None,None,None,None,None,None],
        [None,None,None,None,None,None,None,None],
        [None,None,None,None,None,None,None,None],
        [None,None,None,None,None,None,None,None],
        [None,None,None,None,None,None,None,None]
        ]
    
    for index, piece in enumerate(piece_order):
        for loc in piece_locations[index]: #gets a piece's location on the board in form (letter-index. num-index)) etc.
            number = loc[1]
            letter_idx = loc[0]
            fen_list[7-number][letter_idx] = piece #7-number to flip coords
    
    #compress nones
    fen_list_edited = []
    
    for row in fen_list:
        res_row = []
        count = 0
        for item in row:
            if item is None:
                count += 1
            else:
                if count > 0:
                    res_row.append(count)
                    count = 0
                res_row.append(item)
        if count > 0:
            res_row.append(count)
        
        fen_list_edited.append(res_row)

    fen = '/'.join(''.join(str(x) for x in row) for row in fen_list_edited)
    return fen

########################################################################## MAIN SCRIPT
foreground = win32gui.GetForegroundWindow()
win32gui.ShowWindow(foreground, win32con.SW_MAXIMIZE)

print("WARNING: PLEASE ENSURE THAT: SCALE IS SET TO 100 PERCENT AND RESOLUTION IS 1600x900\n")
print("ALSO, MAKE SURE YOU ARE USING THE CORRECT BOARD (looks brown and fuzzy) AND PIECES (looks like default but no shading)")
print("IF BUG OCCURS, TAB OUT OF CHESS.COM AND THEN BACK IN")

if getattr(sys, 'frozen', False):  # Running as exe
    project_dir = Path(sys._MEIPASS)
else:  # Running as script
    project_dir = Path(__file__).parent

set_depth = int(input("Please enter stockfish depth from 1-17: "))
while set_depth > 17 or set_depth < 1:
    set_depth = int(input("Please enter stockfish depth from 1-17: "))

speed = int(input("Please enter speed from 1-100: "))
while speed > 100 or speed < 1:
    speed = int(input("Please enter speed from 1-100: "))

print("\nWaiting for game start...")

stockfish = Stockfish(path = project_dir / "stockfish" / "stockfish-windows-x86-64-avx2.exe", depth=set_depth, parameters={"Threads": 3, "Minimum Thinking Time": 0.01})

game_end = cv.imread(project_dir / "assets" / "game_end.png", cv.COLOR_RGBA2RGB)
game_aborted = cv.imread(project_dir / "assets" / "game_aborted.png", cv.COLOR_RGBA2RGB)

piece_paths = [
    project_dir / "assets" / "blackbishop.png",
    project_dir / "assets" / "blackking.png",
    project_dir / "assets" / "blackknight.png",
    project_dir / "assets" / "blackpawn.png",
    project_dir / "assets" / "blackqueen.png",
    project_dir / "assets" / "blackrook.png",
    
    project_dir / "assets" / "whitebishop.png",
    project_dir / "assets" /"whiteking.png",
    project_dir / "assets" / "whiteknight.png",
    project_dir / "assets" / "whitepawn.png",
    project_dir / "assets" / "whitequeen.png",
    project_dir / "assets" / "whiterook.png"
    ]

#works on 1600x900 - to change for different resolutions find the pixel of top left of chessboard
x1 = 231
y1 = 104
x2 = 828
y2 = 832
w = x2-x1
h = y2-y1
t = 5
square_size = 75
y1_board = 153
y2_board = 752

toggle = False
is_white = None

while True:
    screenshot = get_screenshot(x1, y1, w, h)

    # cv.imshow("screen", screenshot)
    # if cv.waitKey(1) == ord("q"):
    #     cv.destroyAllWindows()
    #     break
    
    gameendcomp = cv.matchTemplate(game_end, screenshot, cv.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv.minMaxLoc(gameendcomp)
    if max_val > 0.9:
        print("Game ended, recheck for side")
        is_white = None

    gameabortedcomp = cv.matchTemplate(game_aborted, screenshot, cv.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv.minMaxLoc(gameabortedcomp)
    if max_val > 0.9:
        print("Game ended, recheck for side")
        is_white = None

    if is_white is None:
        #check for colour white on timer to know if you are playing white (and it is your turn)
        if tuple(screenshot[h-t, w-t]) == (np.uint8(255), np.uint8(255), np.uint8(255)):
            my_timer_colour = (np.uint8(255), np.uint8(255), np.uint8(255))
            is_white = True
            print("Playing white")
        #check for colour greyish on timer to know if you are playing black (and it is your turn)
        elif tuple(screenshot[h-t, w-t]) == (np.uint8(33), np.uint8(36), np.uint8(38)):
            my_timer_colour = (np.uint8(33),np.uint8(36),np.uint8(38))
            is_white = False
            print("Playing black")
    
    if is_white is None:
        continue
    
    piece_locations = []

    if tuple(screenshot[h-t, w-t]) != my_timer_colour:
        if toggle:
            print('Their move, waiting...\n')

        toggle = False
        
    elif tuple(screenshot[h-t, w-t]) == my_timer_colour:
        if not toggle:
            print('My move!')

        #1. RECORD BOARD POSITION
            fen = make_fen()
            
            #edit fen for turn
            if is_white:
                fen += ' w'
            else:
                fen += ' b'
            
            stockfish.set_fen_position(fen)
            print(fen)
            print('Position after their move', stockfish.get_board_visual())

        #2. MAKE MY MOVE
            move_to_make = stockfish.get_best_move()     
            
            #get locations to click to make the move
            char1 = move_to_make[0]
            num1 = int(move_to_make[1])
            char2 = move_to_make[2]
            num2 = int(move_to_make[3])

            if is_white:
                init_x = x1 + square_size//2 + square_size*(ord(char1) - ord('a'))
                init_y = y2_board - square_size//2 - square_size*(num1 - 1)
                future_x = x1 + square_size//2 + square_size*(ord(char2) - ord('a'))
                future_y = y2_board - square_size//2 - square_size*(num2 - 1)
            else:
                init_x = x2 - square_size//2 - square_size*(ord(char1) - ord('a'))
                init_y = y1_board + square_size//2 + square_size*(num1 - 1)
                future_x = x2 - square_size//2 - square_size*(ord(char2) - ord('a'))
                future_y = y1_board + square_size//2 + square_size*(num2 - 1)

            #random move time from 0 to 1 sec
            rand = random.random()
            pg.PAUSE = rand/(speed)

            #click on init loc
            pg.moveTo(init_x, init_y)
            pg.mouseDown(button="left")

            #drag to future loc
            pg.moveTo(future_x, future_y)
            pg.mouseUp(button="left")

            #make move on stockfish
            stockfish.make_moves_from_current_position([move_to_make])
            print("Position after my move", move_to_make, stockfish.get_board_visual())


        toggle = True
