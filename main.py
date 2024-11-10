import pygame, sys, pygame_gui
import multiprocessing
from button import Button
import math
import sqlite3
import time
import pyvisa as visa
import json

# load config file
with open('config.json', 'r', encoding='utf-8') as file:
    config_data = json.load(file)

# remote devices
# counter
rm = visa.ResourceManager()
instr_cnt100 = rm.open_resource(config_data['cnt100'])
instr_cnt100.timeout = 25000

# gate generator
instr_cnt91 = rm.open_resource(config_data['cnt91'])
instr_cnt91.timeout = 1000
print(instr_cnt100.query('*IDN?'))
print(instr_cnt91.query('*IDN?'))


pygame.init()

# Creating database connection
conn = sqlite3.connect(config_data['databasename'])
c = conn.cursor()

# Creating database if doesnt exists
c.execute('''
    CREATE TABLE IF NOT EXISTS scores
    (player TEXT, bestscore REAL, attempt1 REAL, attempt2 REAL, attempt3 REAL)
''')

# common commands
reset = '*RST'
clear = '*CLS'

# generator commands
output = 'PULSe' # 'OFF' to low level no activity
pulse_period = ':SOURce:PULSe:PERiod ' + config_data['pulse_period']
pulse_width = ':SOURce:PULSe:WIDTh ' + config_data['pulse_width']

instr_cnt91.write(reset)
instr_cnt91.write(clear)
instr_cnt100.write(reset)
instr_cnt100.write(clear)

# Check available screens
display_info = pygame.display.get_desktop_sizes()

# Get Main screen size
screen_width, screen_height = display_info[0]

print(f"Screen sizes: {display_info}")
print(f"Number of screens: {len(display_info)}")
print(f"SCREEN 1: {display_info[0]}")

# Get secondary screen size
if len(display_info) > 1:
    screen_width_secondary, screen_height_secondary = display_info[1]
    print(f"SCREEN 2: {display_info[1]}")

SCORE_BOARD_BG = pygame.image.load("assets/Score Board Background.jpg")

# Colors
RED = (255, 78, 78)
GRAY = (63, 63, 63)
LIGHT_GRAY = (150, 150, 150)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
ORANGE = (255,215,0)

# Plot
AXIS_X_START_POINT_X = screen_width * 0.2
AXIS_X_START_POINT_Y = screen_height * 0.50
AXIS_X_END_POINT_X = screen_width * 0.8
AXIS_X_END_POINT_Y = screen_height * 0.50

AXIS_Y_START_POINT_X = screen_width * 0.2
AXIS_Y_START_POINT_Y = screen_height * 0.2
AXIS_Y_END_POINT_X = screen_width * 0.2
AXIS_Y_END_POINT_Y = screen_height * 0.8

# Creating manager
manager = pygame_gui.UIManager((screen_width, screen_height))

# Dodanie czcionki do managera
manager.ui_theme.get_font_dictionary().add_font_path('custom_font', "assets/font.ttf")

# Teraz tworzysz zmienną theme jako słownik
theme = {
    "#main_text_entry": {
        "colours": {
            "dark_bg": "#00000000",
            "normal_text": "#FF4E4E"
        },
        "font": {
            "name": "custom_font",  # ustawiamy nazwę wcześniej załadowanej czcionki
            "size": 40               # rozmiar czcionki
        }
    }
}

manager.ui_theme.load_theme(theme)

clock = pygame.time.Clock()

PLAYER_NAME = ""
PLAYER_SCORE = 0
scores = []

PLAY_TEXT_INPUT = pygame_gui.elements.UITextEntryLine(relative_rect=pygame.Rect((screen_width / 4, 400), (1000, 100)), manager=manager,
                                               object_id='#main_text_entry')
PLAY_TEXT_INPUT.set_text_length_limit(18)  # Ustawienie limitu na 20 znaków

def main_screen():
    SCREEN = pygame.display.set_mode((0, 0),pygame.FULLSCREEN, display=0)
    pygame.display.set_caption("GAME")
    return SCREEN

def secondary_screen():
    SCREEN = pygame.display.set_mode((0, 0),pygame.FULLSCREEN, display=1)
    pygame.display.set_caption("SCORE BOARD")
    return SCREEN

def get_font(size):
    return pygame.font.Font("assets/font.ttf", size)

# Funkcja do dodawania wyników gracza
# def add_scores(c, conn, player, best_score, attempt1, attempt2, attempt3):
#     c.execute("INSERT INTO scores (player, bestscore, attempt1, attempt2, attempt3) VALUES (?, ?, ?, ?, ?)", 
#               (player, best_score, attempt1, attempt2, attempt3))
#     conn.commit()

def add_scores_or_update(c, conn, player, best_score, attempt1, attempt2, attempt3):

    # Sprawdzanie, czy gracz już istnieje
    c.execute("SELECT 1 FROM scores WHERE player = ?", (player,))
    if c.fetchone():
        # Jeśli gracz istnieje, aktualizujemy jego wyniki
        c.execute('''
            UPDATE scores
            SET bestscore = ?, attempt1 = ?, attempt2 = ?, attempt3 = ?
            WHERE player = ?
        ''', (best_score, attempt1, attempt2, attempt3, player))
        print(f"Nadpisano wyniki gracza '{player}'.")
    else:
        # Jeśli gracz nie istnieje, dodajemy nowy rekord
        c.execute('''
            INSERT INTO scores (player, bestscore, attempt1, attempt2, attempt3)
            VALUES (?, ?, ?, ?, ?)
        ''', (player, best_score, attempt1, attempt2, attempt3))
        print(f"Dodano nowego gracza '{player}'.")

    # Zatwierdzenie zmian
    conn.commit()
    conn.close()

def get_best_scores(c, limit=10):
    c.execute("SELECT * FROM scores ORDER BY bestscore ASC LIMIT ?", (limit,))
    return c.fetchall()

def clear_database(c, conn):
    # Usunięcie wszystkich rekordów z tabeli 'wyniki'
    c.execute("DELETE FROM scores")
    # Zatwierdzenie zmian
    conn.commit()
    # Zamknięcie połączenia
    conn.close()

# Funkcja sprawdzająca, czy gracz o podanej nazwie już istnieje w tabeli
def nickname_exists(c, conn, gracz):
    # Zapytanie SQL sprawdzające istnienie gracza
    c.execute("SELECT 1 FROM scores WHERE player = ?", (gracz,))
    wynik = c.fetchone()

    # Zamknięcie połączenia
    conn.close()

    # Jeśli wynik nie jest pusty (istnieje rekord), zwróć True
    return wynik is not None

# setting device generator
def init_generator_settings():
    instr_cnt91.write(reset)
    instr_cnt91.write(clear)
    instr_cnt91.write(pulse_period)
    instr_cnt91.write(pulse_width)
    instr_cnt91.query('*OPC?')

# setting counter
def init_counter_settings():
    instr_cnt100.write(reset)
    instr_cnt100.write(clear)
    instr_cnt100.write(':SYST:CONF "Function=PeriodSingle A; SampleCount=1; SampleInterval=200E-3; TriggerModeA=Manual; AbsoluteTriggerLevelA=0.5; ImpedanceA=50 Ohm; CouplingA=DC"')
    instr_cnt100.query('*OPC?')
    print(instr_cnt100.query(':SYST:ERR?'))

def draw_axes(screen, num_markers=3, duration=3, finish = 3):
    # Oś X
    pygame.draw.line(screen, LIGHT_GRAY, (AXIS_X_START_POINT_X, AXIS_X_START_POINT_Y), (AXIS_X_END_POINT_X, AXIS_X_END_POINT_Y), 10)
    # Oś Y
    pygame.draw.line(screen, LIGHT_GRAY, (AXIS_Y_START_POINT_X, AXIS_Y_START_POINT_Y), (AXIS_Y_END_POINT_X, AXIS_Y_END_POINT_Y), 10)

    # Oblicz odstęp między znacznikami
    step = (AXIS_X_END_POINT_X - AXIS_X_START_POINT_X) / num_markers
    for i in range(num_markers + 1):
        marker_x = AXIS_X_START_POINT_X + i * step  # Pozycja znacznika
        pygame.draw.line(screen, LIGHT_GRAY, (marker_x, AXIS_X_END_POINT_Y - 10),
                         (marker_x, AXIS_X_END_POINT_Y + 10), 10)  # Znacznik

        # Etykieta z czasem dla znaczników pośrednich
        if i > 0 and i != finish:  # Tylko dla znaczników 1s i 2s
            label = get_font(15).render(f"{i * (duration / num_markers):.1f}s", True, LIGHT_GRAY)
            screen.blit(label, (marker_x - 10, AXIS_X_END_POINT_Y + 20))  # Tekst obok znacznika

    # Znacznik FINISH
    finish_marker_x = AXIS_X_START_POINT_X + step * (finish)
    pygame.draw.line(screen, LIGHT_GRAY, (finish_marker_x, AXIS_X_END_POINT_Y - 10),
                     (finish_marker_x, AXIS_X_END_POINT_Y + 10), 10)
    finish_label = get_font(15).render(f"FINISH!", True, LIGHT_GRAY)
    screen.blit(finish_label, (finish_marker_x - 50, AXIS_X_END_POINT_Y + 20))  # Tekst obok znacznika

def play(screen):
    PLAY_TEXT_INPUT.set_text("")
    PLAY_TEXT_INPUT.focus()
    nickname_failure = False
    nickname_empty = False
    running = True
    while running:
        PLAY_MOUSE_POS = pygame.mouse.get_pos()

        screen.fill("black")

        PLAY_TEXT = get_font(45).render("Type your nickname...", True, LIGHT_GRAY)
        PLAY_RECT = PLAY_TEXT.get_rect(center=(screen_width / 2, 260))
        screen.blit(PLAY_TEXT, PLAY_RECT)

        if nickname_failure:
            nickname_empty = False
            NICKNAME_FAILURE_TEXT = get_font(35).render("nickname alredy exist!", True, RED)
            NICKNAME_FAILURE_RECT = NICKNAME_FAILURE_TEXT.get_rect(center=(screen_width / 2, 340))
            screen.blit(NICKNAME_FAILURE_TEXT, NICKNAME_FAILURE_RECT)
        
        if nickname_empty:
            NICKNAME_EMPTY_TEXT = get_font(35).render("text box is empty!", True, RED)
            NICKNAME_EMPTY_RECT = NICKNAME_EMPTY_TEXT.get_rect(center=(screen_width / 2, 340))
            screen.blit(NICKNAME_EMPTY_TEXT, NICKNAME_EMPTY_RECT)

        PLAY_BACK = Button(image=pygame.image.load("assets/Back Rect.png"), pos=(screen_width / 2 - 450, 660), 
                            text_input="BACK", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)
        
        PLAY_CLEAR = Button(image=pygame.image.load("assets/Clear Start Rect.png"), pos=(screen_width / 2, 660), 
                            text_input="CLEAR", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)

        PLAY_START = Button(image=pygame.image.load("assets/Clear Start Rect.png"), pos=(screen_width / 2 + 470, 660), 
                            text_input="START", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)

        PLAY_BACK.changeColor(PLAY_MOUSE_POS)
        PLAY_BACK.update(screen)

        PLAY_CLEAR.changeColor(PLAY_MOUSE_POS)
        PLAY_CLEAR.update(screen)

        PLAY_START.changeColor(PLAY_MOUSE_POS)
        PLAY_START.update(screen)

        UI_REFRESH_RATE = clock.tick(60)/1000

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if PLAY_BACK.checkForInput(PLAY_MOUSE_POS):
                    main_game_window()
                    running = False
                if PLAY_CLEAR.checkForInput(PLAY_MOUSE_POS):
                    PLAY_TEXT_INPUT.set_text("")
                if PLAY_START.checkForInput(PLAY_MOUSE_POS):
                    PLAYER_NAME = PLAY_TEXT_INPUT.get_text()
                    if len(PLAYER_NAME) > 0:
                        conn = sqlite3.connect(config_data['databasename'])
                        c = conn.cursor()
                        if nickname_exists(c, conn, PLAYER_NAME):
                            nickname_failure = True
                        else:
                            countdown(PLAYER_NAME, screen)
                            running = False
                    else:
                        nickname_empty = True

            manager.process_events(event)
        
        manager.update(UI_REFRESH_RATE)

        manager.draw_ui(screen)

        pygame.display.update()

def countdown(player_nickname, screen):
    countdown_start = 4  # Początkowa wartość odliczania
    countdown_time = 0  # Zmienna do przechowywania czasu odliczania
    init_generator_settings()
    init_counter_settings()
    running = True
    while running:
        screen.fill("black")

        # Sprawdzenie, czy odliczanie się odbywa
        if countdown_start > 0:
            countdown_text = get_font(100).render(str(countdown_start), True, LIGHT_GRAY)
            countdown_rect = countdown_text.get_rect(center=(screen_width / 2, screen_height / 2))
            screen.blit(countdown_text, countdown_rect)

            # Sprawdź, czy czas na odliczanie
            if pygame.time.get_ticks() - countdown_time >= 1000:
                countdown_start -= 1
                countdown_time = pygame.time.get_ticks()  # Zresetuj czas odliczania
        else:
            play_attempts(player_nickname, screen, 3)
            running = False

        pygame.display.update()

def score(player_nickname, scores, best_score, screen):
    running = True
    while running:
        OPTIONS_MOUSE_POS = pygame.mouse.get_pos()

        screen.fill("black")

        OPTIONS_EXIT = Button(image=pygame.image.load("assets/Back Rect.png"), pos=(screen_width / 2 - 300, 100),
                                text_input="EXIT", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)
        OPTIONS_REPLAY = Button(image=pygame.image.load("assets/Replay Rect.png"), pos=(screen_width / 2 + 300, 100),
                                text_input="REPLAY", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)

        OPTIONS_EXIT.changeColor(OPTIONS_MOUSE_POS)
        OPTIONS_EXIT.update(screen)
        OPTIONS_REPLAY.changeColor(OPTIONS_MOUSE_POS)
        OPTIONS_REPLAY.update(screen)

        player_score = get_font(35).render(F"PLAYER: {player_nickname}", True, LIGHT_GRAY)
        player_score_rect = player_score.get_rect(center=(screen_width / 2, screen_height / 5 + 50))

        attempt1_text = get_font(20).render(f"1 attempt: accuracy = {scores[0]:.13f} s", True, LIGHT_GRAY)
        attempt1_rect = attempt1_text.get_rect(center=(screen_width / 2, screen_height / 4 + 100))

        attempt2_text = get_font(20).render(f"2 attempt: accuracy = {scores[1]:.13f} s", True, LIGHT_GRAY)
        attempt2_rect = attempt2_text.get_rect(center=(screen_width / 2, screen_height / 3 + 150))

        attempt3_text = get_font(20).render(f"3 attempt: accuracy = {scores[2]:.13f} s", True, LIGHT_GRAY)
        attempt3_rect = attempt2_text.get_rect(center=(screen_width / 2, screen_height / 2 + 100))

        best_score_text = get_font(20).render(f"Best score: accuracy = {best_score:.13f} s", True, RED)
        best_score_rect = best_score_text.get_rect(center=(screen_width / 2, screen_height / 1.5 + 50))

        screen.blit(player_score, player_score_rect)
        screen.blit(attempt1_text, attempt1_rect)
        screen.blit(attempt2_text, attempt2_rect)
        screen.blit(attempt3_text, attempt3_rect)
        screen.blit(best_score_text, best_score_rect)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if OPTIONS_EXIT.checkForInput(OPTIONS_MOUSE_POS):
                    main_game_window()
                    running = False
                if OPTIONS_REPLAY.checkForInput(OPTIONS_MOUSE_POS):
                    countdown(player_nickname, screen)
                    #play_attempts(player_nickname, screen, 3)
                    running = False

        pygame.display.update()

def play_start(screen, attempt):
    # Zmienne do rysowania sinusoidy
    drawing = False
    start_time = 0
    duration = 7  # Czas trwania w sekundach
    num_of_tags = 7
    finish = 3
    frequency = 5 * math.pi / duration  # Częstotliwość
    amplitude = 150  # Amplituda sinusoidy
    points = []  # Lista punktów do rysowania

    countdown_start = 4  # Początkowa wartość odliczania
    countdown_time = 0  # Zmienna do przechowywania czasu odliczania

    gate_open = True

    gate_close = True

    running = True

    while running:
        screen.fill("black")

        if attempt == 1:
            ATTEMPT_TEXT = get_font(25).render(f"{attempt} attempt", True, RED)
            ATTEMPT_RECT = ATTEMPT_TEXT.get_rect(center=(screen_width / 2, 100))
            screen.blit(ATTEMPT_TEXT, ATTEMPT_RECT)
            if not drawing:
                drawing = True
                start_time = pygame.time.get_ticks()  # Zapisz czas rozpoczęcia
                points.clear()  # Wyczyść punkty przed nowym rysowaniem
        else:
            if countdown_start == 4:
                init_generator_settings()
                init_counter_settings()
            if not drawing:
                # Sprawdzenie, czy odliczanie się odbywa
                if countdown_start > 0:

                    # Sprawdź, czy czas na odliczanie
                    if pygame.time.get_ticks() - countdown_time >= 1000:
                        countdown_start -= 1
                        countdown_time = pygame.time.get_ticks()  # Zresetuj czas odliczania

                    ATTEMPT_TEXT = get_font(25).render(f"{attempt} attempt in {countdown_start}s", True, RED)
                    ATTEMPT_RECT = ATTEMPT_TEXT.get_rect(center=(screen_width / 2, 100))
                    screen.blit(ATTEMPT_TEXT, ATTEMPT_RECT)
                else:
                    drawing = True
                    start_time = pygame.time.get_ticks()  # Zapisz czas rozpoczęcia
                    points.clear()  # Wyczyść punkty przed nowym rysowaniem

        PLAY_TEXT = get_font(25).render("Tap 'enter' or 'space' on keyboard to stop time count!", True, LIGHT_GRAY)
        PLAY_RECT = PLAY_TEXT.get_rect(center=(screen_width / 2, 60))
        screen.blit(PLAY_TEXT, PLAY_RECT)

        if drawing:
            ATTEMPT_TEXT = get_font(25).render(f"{attempt} attempt", True, RED)
            ATTEMPT_RECT = ATTEMPT_TEXT.get_rect(center=(screen_width / 2, 100))
            screen.blit(ATTEMPT_TEXT, ATTEMPT_RECT)

        # Rysuj osie
        draw_axes(screen, num_of_tags, duration, finish)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:  # Naciśnij Enter lub spacje, aby zatrzymać rysowanie
                    if drawing:
                        if gate_close:
                            # close gate
                            output = 'PULSe'
                            instr_cnt91.write(':OUTPut:TYPE ' + output)
                            print("Gate close pulse HIGH")
                            time.sleep(config_data['rise']) # to opoznienie jest wazne, inaczej licznik nie "zlapie" zbocza 
                            output = 'OFF'
                            instr_cnt91.write(':OUTPut:TYPE ' + output)
                            print("Gate close pulse LOW")
                            instr_cnt91.query('*OPC?')
                            instr_cnt100.query('*OPC?')
                            data_str = instr_cnt100.query(':FETCH:ARRAY? MAX, A')
                            data_str = data_str.strip()  # to remove \n at the end
                            if len(data_str) > 0:
                                data = list(map(float, data_str.split(',')))  # Convert the string to python array
                            else:
                                data = []
                            elapsed_time = (pygame.time.get_ticks() - start_time) / 1000  # Czas w sekundach
                            drawing = False  # Zatrzymaj rysowanie, ale nie możesz już tego zrobić ponownie
                            running = False
                            gate_close = False
                            return data[0]
                            #return elapsed_time

        if drawing:
            if gate_open:
            # open gate
                output = 'PULSe'
                instr_cnt100.write(':INIT')
                instr_cnt91.write(':OUTPut:TYPE ' + output)
                print("Gate open pulse HIGH")
                time.sleep(config_data['rise']) # to opoznienie jest wazne, inaczej licznik nie "zlapie" zbocza 
                output = 'OFF'
                instr_cnt91.write(':OUTPut:TYPE ' + output)
                print("Gate open pulse LOW")
                instr_cnt91.query('*OPC?')
                gate_open = False

            # Oblicz upłynięty czas
            elapsed_time = (pygame.time.get_ticks() - start_time) / 1000  # Czas w sekundach
            
            # Rysuj nowe punkty sinusoidy w czasie rzeczywistym
            if elapsed_time <= duration:  # Upewnij się, że nie przekraczamy duration
                # Oblicz wartość y na podstawie upływu czasu
                y = AXIS_X_START_POINT_Y - amplitude * math.sin(frequency * elapsed_time)  # Użyj upływu czasu w sinusoidzie
                points.append((int(AXIS_X_START_POINT_X + (elapsed_time / duration) * (AXIS_X_END_POINT_X - AXIS_X_START_POINT_X)), int(y)))  # Dodaj punkt do listy
            else:
                if gate_close:
                    # close gate
                    output = 'PULSe'
                    instr_cnt91.write(':OUTPut:TYPE ' + output)
                    print("Gate close pulse HIGH")
                    time.sleep(config_data['rise']) # to opoznienie jest wazne, inaczej licznik nie "zlapie" zbocza 
                    output = 'OFF'
                    instr_cnt91.write(':OUTPut:TYPE ' + output)
                    print("Gate close pulse LOW")
                    instr_cnt91.query('*OPC?')
                    instr_cnt100.query('*OPC?')
                    data_str = instr_cnt100.query(':FETCH:ARRAY? MAX, A')
                    data_str = data_str.strip()  # to remove \n at the end
                    if len(data_str) > 0:
                        data = list(map(float, data_str.split(',')))  # Convert the string to python array
                    else:
                        data = []
                    elapsed_time = (pygame.time.get_ticks() - start_time) / 1000  # Czas w sekundach
                    drawing = False  # Zatrzymaj rysowanie, ale nie możesz już tego zrobić ponownie
                    running = False
                    gate_close = False
                    return data[0]
            
            # Rysuj wszystkie punkty
            for point in points:
                pygame.draw.circle(screen, RED, point, 2)  # Rysuj punkty sinusoidy

        pygame.display.update()

def play_attempts(player_nickname, screen, attempts):
    # Tworzenie połączenia z bazą danych
    conn = sqlite3.connect(config_data['databasename'])
    c = conn.cursor()
    scores = []
    absolute_value_scores = []
    reference_value = 3.0000000000000
    attempt = 0
    best_score = 0.0000000000000
    for attempt in range (attempts):
        elapsed_time = play_start(screen, attempt + 1)
        scores.append(elapsed_time)

    for i in range(len(scores)):
        absolute_value_scores.append(abs(scores[i] - reference_value))

    best_score = min(absolute_value_scores)

    add_scores_or_update(c, conn, player_nickname, best_score, absolute_value_scores[0], absolute_value_scores[1], absolute_value_scores[2])

    score(player_nickname, absolute_value_scores, best_score, screen)

def options(screen):
    conn = sqlite3.connect(config_data['databasename'])
    c = conn.cursor()
    running = True
    while running:
        OPTIONS_MOUSE_POS = pygame.mouse.get_pos()

        screen.fill("black")

        OPTIONS_TEXT = get_font(45).render("This is the OPTIONS screen.", True, LIGHT_GRAY)
        OPTIONS_RECT = OPTIONS_TEXT.get_rect(center=(screen_width / 2, 260))
        screen.blit(OPTIONS_TEXT, OPTIONS_RECT)

        OPTIONS_CLEAR_DATABASE = Button(image=pygame.image.load("assets/Replay Rect.png"), pos=(screen_width / 2, 460), 
                            text_input="CLEAR", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)

        OPTIONS_CLEAR_DATABASE.changeColor(OPTIONS_MOUSE_POS)
        OPTIONS_CLEAR_DATABASE.update(screen)

        OPTIONS_BACK = Button(image=pygame.image.load("assets/Back Rect.png"), pos=(screen_width / 2, 660), 
                            text_input="BACK", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)

        OPTIONS_BACK.changeColor(OPTIONS_MOUSE_POS)
        OPTIONS_BACK.update(screen)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if OPTIONS_CLEAR_DATABASE.checkForInput(OPTIONS_MOUSE_POS):
                    clear_database(c, conn)
                if OPTIONS_BACK.checkForInput(OPTIONS_MOUSE_POS):
                    main_game_window()
                    running = False

        pygame.display.update()

def main_game_window():
    pygame.init()
    SCREEN = main_screen()
    pygame.display.set_caption("Okno 1")

    running = True
    while running:
        SCREEN.fill("black")

        MENU_MOUSE_POS = pygame.mouse.get_pos()

        MENU_TEXT = get_font(100).render("MAIN MENU", True, RED)
        MENU_RECT = MENU_TEXT.get_rect(center=(screen_width / 2, 100))

        PLAY_BUTTON = Button(image=pygame.image.load("assets/Play Rect.png"), pos=(screen_width / 2, 350), 
                            text_input="PLAY", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)
        OPTIONS_BUTTON = Button(image=pygame.image.load("assets/Options Rect.png"), pos=(screen_width / 2, 500), 
                            text_input="OPTIONS", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)
        QUIT_BUTTON = Button(image=pygame.image.load("assets/Quit Rect.png"), pos=(screen_width / 2, 650), 
                            text_input="QUIT", font=get_font(75), base_color=LIGHT_GRAY, hovering_color=RED)

        SCREEN.blit(MENU_TEXT, MENU_RECT)

        for button in [PLAY_BUTTON, OPTIONS_BUTTON, QUIT_BUTTON]:
            button.changeColor(MENU_MOUSE_POS)
            button.update(SCREEN)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if PLAY_BUTTON.checkForInput(MENU_MOUSE_POS):
                    play(SCREEN)
                    running = False
                if OPTIONS_BUTTON.checkForInput(MENU_MOUSE_POS):
                    options(SCREEN)
                    running = False
                if QUIT_BUTTON.checkForInput(MENU_MOUSE_POS):
                    pygame.quit()
                    sys.exit()

        pygame.display.update()

def score_board_window(main_window_running=True):
    # Tworzenie połączenia z bazą danych
    conn = sqlite3.connect(config_data['databasename'])
    c = conn.cursor()
    pygame.init()
    SCREEN = secondary_screen()
    pygame.display.set_caption("Okno 2")

    scroll_offset = 0  # Przesunięcie scrolla
    max_scroll = 0     # Maksymalne przewinięcie

    while main_window_running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                main_window_running = False
            elif event.type == pygame.MOUSEWHEEL:
                # Przewijanie góra/dół za pomocą kółka myszy
                scroll_offset += event.y * 20  # 60 pikseli na jedno przewinięcie
                scroll_offset = max(min(scroll_offset, 0), -max_scroll)

        top10_scores = get_best_scores(c, limit=1000)
        place = 1
        scores_height = 700 + scroll_offset
        scores_width = 10
        attempts_height = 680 + scroll_offset

        SCREEN.blit(SCORE_BOARD_BG, (0, 0))

        # Nagłówek tabeli
        SCORE_BOARD_TEXT = get_font(80).render("SCORE BOARD", True, ORANGE)
        SCORE_BOARD_TEXT_RECT = SCORE_BOARD_TEXT.get_rect(center=(screen_width_secondary / 2, screen_height_secondary / 4 + 50))
        SCREEN.blit(SCORE_BOARD_TEXT, SCORE_BOARD_TEXT_RECT)

        SCORE_BOARD_HEADER_TEXT = get_font(15).render("- PLAYER NAME ------------- BEST SCORE ---------------- ATTEMPTS -----", True, RED)
        SCORE_BOARD_HEADER_RECT = SCORE_BOARD_HEADER_TEXT.get_rect(center=(screen_width_secondary / 2, screen_height_secondary / 3))
        SCREEN.blit(SCORE_BOARD_HEADER_TEXT, SCORE_BOARD_HEADER_RECT)

        # Wyświetlanie wyników
        for rekord in top10_scores:
            # Sprawdzamy, czy wpis znajduje się w widocznym obszarze
            if screen_height_secondary / 3 + 40 < scores_height < screen_height_secondary - 40:
                SCORE_BOARD_PLACE_TEXT = get_font(15).render(f"{place}.", True, ORANGE)
                SCORE_BOARD_PLACE_RECT = SCORE_BOARD_PLACE_TEXT.get_rect(topleft=(scores_width, scores_height))

                SCORE_BOARD_PLAYER_NAME_TEXT = get_font(15).render(f"{rekord[0]}", True, WHITE)
                SCORE_BOARD_PLAYER_NAME_RECT = SCORE_BOARD_PLAYER_NAME_TEXT.get_rect(topleft=(scores_width + 50, scores_height))

                SCORE_BOARD_BEST_SCORE_TEXT = get_font(15).render(f"{rekord[1]}", True, ORANGE)
                SCORE_BOARD_BEST_SCORE_RECT = SCORE_BOARD_BEST_SCORE_TEXT.get_rect(topleft=(scores_width + 370, scores_height))

                SCORE_BOARD_ATTEMPT1_TEXT = get_font(12).render(f"1st. {rekord[2]}", True, WHITE)
                SCORE_BOARD_ATTEMPT1_RECT = SCORE_BOARD_ATTEMPT1_TEXT.get_rect(topleft=(scores_width + 750, attempts_height))

                SCORE_BOARD_ATTEMPT2_TEXT = get_font(12).render(f"2nd. {rekord[3]}", True, WHITE)
                SCORE_BOARD_ATTEMPT2_RECT = SCORE_BOARD_ATTEMPT2_TEXT.get_rect(topleft=(scores_width + 750, attempts_height + 20))

                SCORE_BOARD_ATTEMPT3_TEXT = get_font(12).render(f"3rd. {rekord[4]}", True, WHITE)
                SCORE_BOARD_ATTEMPT3_RECT = SCORE_BOARD_ATTEMPT3_TEXT.get_rect(topleft=(scores_width + 750, attempts_height + 40))

                SCREEN.blit(SCORE_BOARD_PLACE_TEXT, SCORE_BOARD_PLACE_RECT)
                SCREEN.blit(SCORE_BOARD_PLAYER_NAME_TEXT, SCORE_BOARD_PLAYER_NAME_RECT)
                SCREEN.blit(SCORE_BOARD_BEST_SCORE_TEXT, SCORE_BOARD_BEST_SCORE_RECT)
                SCREEN.blit(SCORE_BOARD_ATTEMPT1_TEXT, SCORE_BOARD_ATTEMPT1_RECT)
                SCREEN.blit(SCORE_BOARD_ATTEMPT2_TEXT, SCORE_BOARD_ATTEMPT2_RECT)
                SCREEN.blit(SCORE_BOARD_ATTEMPT3_TEXT, SCORE_BOARD_ATTEMPT3_RECT)

            place += 1
            scores_height += 100
            attempts_height += 100

        # Ustawienie maksymalnego przewijania
        max_scroll = max(0, (place - 1) * 100 - (screen_height_secondary - 300))

        pygame.display.update()

    conn.close()
    pygame.quit()
    
if __name__ == '__main__':
    game_running = True
    multiprocessing.freeze_support()
    print("Running Main GAME process...")
    game_process = multiprocessing.Process(target=main_game_window)
    game_process.start()
    print("Main GAME process alive")
    if len(display_info) > 1:
        print("Running Score board process...")
        time.sleep(1)
        score_board_process = multiprocessing.Process(target=score_board_window)
        score_board_process.start()
        if score_board_process.is_alive():
            print("Score board processalive")
        while game_running:
            if not game_process.is_alive():
                score_board_process.kill()
                game_process.kill()
                game_running = False
    
    if not game_process.is_alive():
        instr_cnt91.write(reset)
        instr_cnt91.write(clear)
        instr_cnt100.write(reset)
        instr_cnt100.write(clear)

    #game_process.join()
    #score_board_process.join()

# Zamknięcie połączenia
conn.close()