import cv2 as cv
import pyautogui as pg
import numpy as np
from PIL import ImageGrab
import time
import win32ui, win32gui, win32con, win32api
from stockfish import Stockfish
from stockfish import models
import random
import sys
from pathlib import Path

def is_fen_valid(fen: str) -> bool:
    temp_sf = Stockfish(path = project_dir / "stockfish" / "stockfish-windows-x86-64-avx2.exe", parameters={"Hash": 1})
    # Using a new temporary SF instance, in case the fen is an illegal position that causes
    # the SF process to crash.
    best_move = None
    temp_sf.set_fen_position(fen, False)
    try:
        best_move = temp_sf.get_best_move()
    except models.StockfishException:
        # If a StockfishException is thrown, then it happened in read_line() since the SF process crashed.
        # This is likely due to the position being illegal, so set the var to false:
        return False
    else:
        return best_move is not None
    finally:
        temp_sf.__del__()
        # Calling this function before returning from either the except or else block above.
        # The __del__ function should generally be called implicitly by python when this
        # temp_sf object goes out of scope, but calling it explicitly guarantees this will happen.

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

def set_pause(turn, speed):
    if tuple(screenshot[h-t, w-t]) == red:
        print("red alert!")
        pg.PAUSE = 0.001
    elif tuple(screenshot[h-t, w-t]) == my_timer_colour:
        print("slow and steady...")
        rand = random.random()
        rand2 = random.random()
        
        if stockfish.will_move_be_a_capture(move_to_make) == Stockfish.Capture.DIRECT_CAPTURE:
            pg.PAUSE = rand/(speed/2)
            print("capture")
        elif 0 <= turn <= 8:
            print("in opening, move faster - turn:", turn)
            pg.PAUSE = (rand/(speed/(turn+1)))/4
        elif 25 <= turn <= 40:
            print("middleish game speed up - turn:", turn)
            if rand2 > 0.4:
                pg.PAUSE = rand/(speed)
            elif rand2 > 0.1:
                pg.PAUSE = rand/(speed/4)
            else:
                pg.PAUSE = rand/(speed/10)
        elif turn >= 40:
            print("endgame nearing, speed up - turn:", turn)
            if rand2 > 0.4:
                pg.PAUSE = rand/(speed)
            elif rand2 > 0.1:
                pg.PAUSE = rand/(speed/2)
            else:
                pg.PAUSE = rand/(speed/4)
        else:
            print("normal happs")
            if rand2 > 0.5:
                pg.PAUSE = rand/(speed/2)
            elif rand2 > 0.2:
                pg.PAUSE = rand/(speed/5)
            else:
                pg.PAUSE = rand/(speed/12)

def make_move_on_screen(move):
    #get locations to click to make the move
    char1 = move[0]
    num1 = int(move[1])
    char2 = move[2]
    num2 = int(move[3])

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

    #click on init loc
    pg.moveTo(init_x, init_y)
    pg.mouseDown(button="left")

    #drag to future loc
    pg.moveTo(future_x, future_y)
    pg.mouseUp(button="left")

def premove(move_made):
    stockfish.make_moves_from_current_position(move_made)

    stockfish.set_elo_rating(2000)
    enemy_move = stockfish.get_best_move()
    stockfish.make_moves_from_current_position(enemy_move)

    stockfish.set_elo_rating(elo_rating)
    premove = stockfish.get_best_move()

    if stockfish.will_move_be_a_capture(premove) == Stockfish.Capture.DIRECT_CAPTURE:
        pg.PAUSE = 0.01
        make_move_on_screen(premove)

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

elo_rating = int(input("Set elo rating (recommend 1000): "))

speed = int(input("Speed (lower is slower) (recommend 8 for bullet): "))

depth = int(input("Depth (recommend 4), increase/decrease slowly: "))

do_premoves = input("Premove? y/n: ")

print("\nWaiting for game start...")

stockfish = Stockfish(path = project_dir / "stockfish" / "stockfish-windows-x86-64-avx2.exe", parameters={"Threads": 3})
stockfish.set_elo_rating(elo_rating)
stockfish.set_depth(depth)

gameend = cv.imread(project_dir / "assets" / "gameend.png", cv.COLOR_RGBA2RGB)
abort = cv.imread(project_dir / "assets" / "abort.png", cv.COLOR_RGBA2RGB)

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
                    
#works on 1920x1080 - to change for different resolutions find the pixel of top left of chessboard
x1 = 231
y1 = 104
x2 = 828
y2 = 832
w = x2-x1
h = y2-y1
t = 3
square_size = 75
y1_board = 153
y2_board = 752

red = (np.uint8(36), np.uint8(31), np.uint8(173))
toggle = False
my_timer_colour = None
is_white = None
turn = 0
side_chosen = False

while True:
    screenshot = get_screenshot(x1, y1, w, h)

    # cv.imshow("screen", screenshot)
    # if cv.waitKey(1) == ord("q"):
    #     cv.destroyAllWindows()
    #     break
    
    gameendcomp = cv.matchTemplate(gameend, screenshot, cv.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv.minMaxLoc(gameendcomp)
    if max_val > 0.9:
        print("Game ended, just look for timer color")
        toggle = False
        turn = 0
        continue

    abortcomp = cv.matchTemplate(abort, screenshot, cv.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv.minMaxLoc(abortcomp)
    if max_val > 0.9:
        print("Game ended, just look for timer color")
        toggle = False
        turn = 0
        continue

    if tuple(screenshot[h-t, w-t]) == (np.uint8(255), np.uint8(255), np.uint8(255)):
        if side_chosen == False:
            my_timer_colour = (np.uint8(255), np.uint8(255), np.uint8(255))
            my_off_timer_colour = (np.uint8(149), np.uint8(151), np.uint8(152))
            is_white = True
            toggle = False
            print("Playing white")
            side_chosen = True

    elif tuple(screenshot[h-t, w-t]) == (np.uint8(33), np.uint8(36), np.uint8(38)):
        if side_chosen == False:
            my_timer_colour = (np.uint8(33),np.uint8(36),np.uint8(38))
            my_off_timer_colour = (np.uint8(37), np.uint8(40), np.uint8(42))
            is_white = False
            toggle = False
            print("Playing black")
            side_chosen = True

    else:
        side_chosen = False

    if my_timer_colour is None:
        continue

    ################################ if in game 

    piece_locations = []

    if tuple(screenshot[h-t, w-t]) == my_off_timer_colour:
        if toggle:
            print('Their move, waiting...\n')
            print(tuple(screenshot[h-t, w-t]))
            toggle = False
        
    elif tuple(screenshot[h-t, w-t]) == my_timer_colour or tuple(screenshot[h-t, w-t]) == red:
        if not toggle:
            print('My move!')
            print(tuple(screenshot[h-t, w-t]))

        #1. RECORD BOARD POSITION
            fen = make_fen()
            
            #edit fen for turn
            if is_white:
                fen += ' w '
                
            else:
                fen += ' b '
            
            if stockfish.get_what_is_on_square('e1') == Stockfish.Piece.WHITE_KING and stockfish.get_what_is_on_square('h1') == Stockfish.Piece.WHITE_ROOK:
                fen += 'K'
            
            if stockfish.get_what_is_on_square('e1') == Stockfish.Piece.WHITE_KING and stockfish.get_what_is_on_square('a1') == Stockfish.Piece.WHITE_ROOK:
                fen += 'Q'
            
            if stockfish.get_what_is_on_square('e8') == Stockfish.Piece.BLACK_KING and stockfish.get_what_is_on_square('h8') == Stockfish.Piece.WHITE_ROOK:
                fen += 'k'
            
            if stockfish.get_what_is_on_square('e8') == Stockfish.Piece.BLACK_KING and stockfish.get_what_is_on_square('a8') == Stockfish.Piece.WHITE_ROOK:
                fen += 'q'

            if is_fen_valid(fen):
                stockfish.set_fen_position(fen)
            else:
                print("fen not valid")
                continue

        #2. MAKE MY MOVE
            move_to_make = stockfish.get_best_move()
            
            set_pause(turn, speed)

            make_move_on_screen(move_to_make)

            #premove captures
            if do_premoves == 'y':
                premove(move_to_make)
                turn += 1
            
            #make move on stockfish
            print("Made move", move_to_make, "based on", fen)

            turn += 1

            toggle = True
