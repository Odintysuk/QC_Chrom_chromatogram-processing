"""

This program is for processing files with chromatography data.
Automatically searches for files with the necessary data in
the program folder. If not, you can download the file from another location.
There is a display of experimental data in the form of a chromatogram graph.
Automatic scaling of the graph from the minimum value to the maximum.
Calculation of necessary parameters based on experimental data

"""
import os
os.environ['KIVY_IMAGE'] = 'pil'

from kivy.config import Config

Config.set('graphics', 'minimum_width', 640)
Config.set('graphics', 'minimum_height', 480)

from kivy.app import App

from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.modalview import ModalView
from kivy.uix.filechooser import FileChooserIconView

from kivy_garden.graph import Graph, MeshLinePlot
from kivy.graphics import (Color, Rectangle, Line)
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import StringProperty, ColorProperty

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.checkbox import CheckBox

from pathlib import Path
from functools import partial
import win32api
import win32file

from GC import chrom


class ScreenMain(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        Window.bind(on_resize=self.resize)

        # main layout contains top and down parts of screen
        bl = BoxLayout(orientation='vertical',
                       size_hint=[1, 1]
                       )

        # top part in main contains graphics and its setups
        self.graph = Graph(xlabel='time, s', ylabel='FID A, pA',
                           label_options={'color': (0,0,0,1)},
                           x_ticks_major=20, y_ticks_major=.5,
                           x_ticks_minor=4, y_ticks_minor=5,
                           background_color=[.91, .96, 1, 1],
                           border_color=[0, 0, 0, 1],
                           tick_color=[0, 0, 0, .3],
                           y_grid_label=True, x_grid_label=True, padding=5,
                           x_grid=True, y_grid=True, ymin=11, ymax=12,
                           xmin=0, xmax=1
                           )
        self.plot = MeshLinePlot(color=[1, 0, 0, 1])
        self.plot.points = chrom.gchrom_sec('')
        self.graph.add_plot(self.plot)

        # down part in main contains left(about filelist) and right(GC params)
        bl_down_master = BoxLayout(orientation='horizontal'
                                   )
        # left in down part with buttons, status bar, help info, list of GC files after scandir
        bl_dm_files_master = BoxLayout(orientation='vertical',
                                       size_hint=[.5, 1],
                                       size_hint_max_x = 480
                                       )

        gl_dm_file_scan = GridLayout(cols=2,
                                     rows=2,
                                     size_hint=[1, 1/3],
                                     size_hint_max_y=105,
                                     padding=2,
                                     spacing=2,
                                     cols_minimum={0: 100, 1: 100},
                                     rows_minimum={0: 25, 1: 25}
                                     )

        self.btn_scan = Button(text='Сканировать',
                               markup = True,
                               size_hint=[1/3, 1],
                               size=[100, gl_dm_file_scan.height/2],
                               size_hint_max=(150, 50),
                               background_color=[.94, .94, .94, 1],
                               background_normal='images/statusbar.png',
                               color=[0, 0, 0, 1],
                               on_press=self.readfile
                               )
                
        # modal view with filechooser
        self.modal_open_file = ModalView(auto_dismiss=False,
                                         size_hint=(.8, .8),
                                         overlay_color=[0, 0, 0, .5],
                                         background_color=(.94, 1, .96, 1),
                                         background='',
                                         on_pre_open=self.scan_local_drives
                                         )
        modal_open_box = BoxLayout(orientation='vertical',
                                   )
        btns_box = BoxLayout(orientation='horizontal',
                             spacing=2,
                             size_hint=(1, .05)
                             )
        self.drives_box = drives_box = BoxLayout(orientation='horizontal',
                                                 size_hint=(1, .05),
                                                 spacing=1
                                                 )
        self.btn_root = Button(text='...',
                               size_hint=(None, 1),
                               width=50,
                               background_color=[.94, 1, .96, 1],
                               background_normal='',
                               background_down='',
                               color=[0, 0, 0, 1],
                               on_press=self.change_drive
                               )
        self.btn_before = self.btn_root
        
        self.icon_view = MyChooser(on_submit=self.submit,
                                   path='.',
                                   dirselect=True,
                                   size_hint=(1, .95),
                                   filters=['*.txt']
                                   )
        btn_load_filechooser = Button(text='Открыть',
                                      background_color=[.94, .94, .94, 1],
                                      background_normal='images/statusbar.png',
                                      color=[0, 0, 0, 1],
                                      on_release=partial(self.load_from_filechooser,
                                                         self.icon_view)
                                      )
        btn_cancel_filechooser = Button(text='Отмена',
                                        background_color=[.94, .94, .94, 1],
                                        background_normal='images/statusbar.png',
                                        color=[0, 0, 0, 1],
                                        on_press=self.modal_open_file.dismiss
                                        )
        # modal view filechooser widgets structure
        self.modal_open_file.add_widget(modal_open_box)
        modal_open_box.add_widget(drives_box)
        modal_open_box.add_widget(self.icon_view)
        modal_open_box.add_widget(btns_box)
        btns_box.add_widget(btn_load_filechooser)
        btns_box.add_widget(btn_cancel_filechooser)

        # calls modal view for choose file
        self.btn_load = Button(text='Открыть файл',
                               markup=True,
                               size_hint=[1/3, 1],
                               size_hint_max=(150, 50),
                               background_color=[.94, .94, .94, 1],
                               background_normal='images/statusbar.png',
                               color=[0, 0, 0, 1],
                               on_press=self.modal_open_file.open
                               )

        # status bar placed in left down part of main,
        # displays the name of the running file
        self.status_bar = Button(text='status',
                                 padding=(5, 0),
                                 font_size=16,
                                 text_size=(Window.width/2-155, 20),
                                 size_hint_max_x = 400,
                                 color=[0, 0, 0, 1],
                                 valign='top',
                                 halign='center',
                                 background_color=(.94, .94, .94, .8),
                                 background_normal='images/statusbar.png',
                                 background_down='images/statusbar.png',
                                 border=[3, 1, 2, 1]
                                 )

        # all about "help button", places in left down part of main
        # contains layouts, button and modalview setups
        bl_btn_help = BoxLayout(orientation='horizontal',
                                size_hint=(2/3, 1)
                                )

        # button help and modal view
        self.modal_help = ModalView(size_hint=(None, None),
                               size=(400, 200),
                               auto_dismiss=True,
                               overlay_color=[0, 0, 0, .2]
                               )
        btn_help = Button(text='',
                          background_normal='images/btn_help.png',
                          size_hint=[1, None],
                          size_hint_max=(30, 35),
                          size_hint_min=(25, 30),
                          size=(30, 30),
                          pos_hint={'top': .85, 'left': 1},
                          background_down='images/btn_help_down.png',
                          on_press=self.modal_help.open
                          )
        # create button of close modal help menu
        btn_modal_help_close = Button(on_press=self.modal_help.dismiss,
                                      background_color=[.94, .94, .94, 1],
                                      background_normal='',
                                      background_down='')
        # create label of help information
        lbl_help = Label(text='[b]Сканировать[/b] - автоматический поиск файлов'
                         '\nс результатами хроматографии в папке с программой.\nСписок файлов '
                         'выводится в нижней части экрана.\nНажмите на имя файла,'
                         'чтобы построить график\nи рассчитать параметры '
                         'хроматографирования.\n\n[b]Открыть файл[/b] - '
                         'подгрузить файл с экспериментальными\nданными и '
                         'получить параметры хроматографирования',
                         markup=True,
                         padding=[10, 10],
                         size_hint=(None, None),
                         size=(350, 150),
                         font_size=14,
                         color=(0, 0, 0, 1),
                         halign='left',
                         valign='center'
                         )
        # add button and label to modal view
        self.modal_help.add_widget(btn_modal_help_close)
        self.modal_help.add_widget(lbl_help)

        # layout contains upper label and list of GC files
        self.bl_file_list = BoxLayout(orientation='vertical',
                                      size_hint=[1, 2/3],
                                      padding=[5, 0, 3, 3]
                                      )

        lbl = Label(text='Файлы с данными хроматографии',
                    markup=True,
                    size_hint_max_y=35,
                    font_size=16,
                    color=[.07, .2, .3, 1]
                    )

        self.scroll_grid = GridLayout(cols=1,
                                 spacing=2,
                                 size_hint_y=None,
                                 size_hint_x=None
                                 )

        self.scroll_grid.bind(minimum_height=self.scroll_grid.setter('height'))
        self.scroll = ScrollView(size_hint=(1, 1),
                                 do_scroll_y=True,
                                 bar_color=[.49, .5, .47, 1],
                                 bar_inactive_color=[.49, .5, .47, .5],
                                 bar_width=3
                                 )
        
        # right in down part with GC parameters
        # the main section with the results of
        # data processing and parameter calcs
        # has a switch for auto- and manual calc modes
        self.out_params = BoxLayout(orientation='vertical',
                                    size_hint=[.5, 1]
                                    )
        self.datetime = BoxLayout(orientation='horizontal',
                                  size_hint=[1, .2],
                                  size_hint_max_y=30)
        self.date_inj = MyLabel(text='Дата и время анализа: ',
                                text_size=[Window.width/2-10, 20])
        self.chrom_comp = BoxLayout(orientation='horizontal',
                                    size_hint=[1, .2],
                                    size_hint_max_y=30,
                                    )
        self.auto_check = BoxLayout(orientation='horizontal',
                                    size_hint=[1, 1],
                                    size_hint_max_y=30,
                                    size_hint_max_x=80
                                    )
        self.checkbox = CheckBox(active=True,
                                 size_hint=[.3, 1],
                                 size_hint_max_x=30)
        self.chrom_params = GridLayout(cols=2,
                                       size_hint=[1, .8])
        

        # structure of main screen widgets
        bl.add_widget(self.graph)
        bl.add_widget(bl_down_master)

        bl_down_master.add_widget(bl_dm_files_master)
        bl_down_master.add_widget(self.out_params)

        self.out_params.add_widget(self.datetime)
        self.datetime.add_widget(self.date_inj)
        self.out_params.add_widget(self.chrom_comp)
        self.out_params.add_widget(self.chrom_params)

        bl_dm_files_master.add_widget(gl_dm_file_scan)
        bl_dm_files_master.add_widget(self.bl_file_list)

        gl_dm_file_scan.add_widget(self.btn_scan)
        gl_dm_file_scan.add_widget(self.status_bar)
        gl_dm_file_scan.add_widget(self.btn_load)
        gl_dm_file_scan.add_widget(bl_btn_help)

        bl_btn_help.add_widget(Widget())
        bl_btn_help.add_widget(btn_help)

        self.bl_file_list.add_widget(lbl)
        self.bl_file_list.add_widget(self.scroll)

        self.add_widget(bl)
    
    def scan_local_drives(self, *args):
        self.drives_box.clear_widgets()
        self.drives_box.add_widget(self.btn_root)
        drives = win32api.GetLogicalDriveStrings()
        drives = drives.split('\000')[:-1]
        for d in drives:
            if win32file.GetDriveType(d) in [0, 1, 5, 6]:
                drives.remove(d)
        for i in drives:
            self.btn_drive = Button(text=i,
                                    size_hint=(None, 1),
                                    width=50,
                                    background_color=[.94, .94, .94, 1],
                                    background_normal='images/statusbar.png',
                                    background_down='',
                                    border=[2, 1, 1, 1],
                                    color=[0, 0, 0, 1],
                                    on_press=self.change_drive
                                    )
            self.drives_box.add_widget(self.btn_drive)
        self.drives_box.add_widget(Button(background_color=[.94, .94, .94, 1],
                                          background_normal='images/statusbar.png',
                                          background_down=''))
       
    def change_drive(self, instance):
        self.btn_before.background_color = [.94, .94, .94, 1]
        self.btn_before.background_normal = 'images/statusbar.png'
        if instance == self.btn_root:
            self.icon_view.path = str('.')
        else:
            self.icon_view.path = str(instance.text)
        instance.background_color = [.94, 1, .96, 1]
        instance.background_normal = ''
        self.btn_before = instance

    def load_from_filechooser(self, icon_view, btn_load):
        self.submit(icon_view.path, icon_view.selection)

    def resize(self, instance,  width, height):
        # changing some options when resizing the window
        self.status_bar.text_size = (Window.width/2-155, 20)
        if self.status_bar.text_size[0] > 300:
            self.status_bar.text_size[0] = 300
        self.date_inj.text_size = [Window.width/2-10, 20]
    
    def readfile(self, instance):
        """Creates buttons for each file in filelist contains GC data
        clicking on the button opens a file with the button's name
        if no files are found in the root directory,
        a widget is created with the message
        
        """
        textfile = []
        self.scroll_grid.clear_widgets()
        self.scroll.clear_widgets()
        # find only *.txt files
        paths = Path('.').glob('*.txt')
        for i in list(map(str, paths)):
            # checks each .txt file on contain GC data
            with open(i, 'r') as inf:
                for n, line in enumerate(inf, 1):
                    line = line.rstrip('\n')
                    if line.find('FID A, pA') != -1:
                        textfile.append(i)
                        continue
        # if no files are found
        if not textfile:
            self.label_empty_list = MyLabel(text='Файлов с данными хроматографии'
                                            '\nв корневой папке программы не '
                                            'обнаружено \nНажмите "Открыть файл" '
                                            'и загрузите данные',
                                            font_size=14,
                                            halign='center'
                                            )
            self.scroll.add_widget(self.label_empty_list)
            return
        for i in textfile:
            self.btn = Button(text=i,
                              color=(0, 0, 0, 1),
                              valign='center',
                              size_hint_x=None,
                              size_hint_y=None,
                              width=Window.width,
                              height=25,
                              background_color=(.94, 1, .96, 1),
                              background_normal='',
                              on_press=self.statusbar
                              )
            self.btn.text_size = [self.btn.width, 25]
            self.scroll_grid.add_widget(self.btn)
        self.scroll.add_widget(self.scroll_grid)

    def param_chrom_auto(self, instance):
        if self.checkbox.active:
            if self.status_bar.text == 'status':
                pass
            else:
                pass

    def params_table(self, filename):
        # calculated parameters representation function
        # receives data on the number of components
        # and displays a table with calculated chromatography parameters
        parameters = {}
        self.chrom_comp.clear_widgets()
        self.chrom_params.clear_widgets()
        self.auto_check.clear_widgets()
        self.chrom_comp.add_widget(self.auto_check)
        self.auto_check.add_widget(self.checkbox)
        self.auto_check.add_widget(MyLabel(text='auto',
                                           size_hint=[.7, 1],
                                           halign='left'))
        self.auto_check.text_size = [self.auto_check.width, 16]
        # checks the number of components
        # components = {'comp': {'param': [values]}}
        components = chrom.findpeaks(filename)
        # sets the number of cols in the table
        self.chrom_params.cols = (len(components) + 1)
        # creates the widget (cell) for each component
        
        for k, v in components.items():
            self.btn = MyLabel(text=k,
                               background_normal='images/statusbar.png',
                               background_down='images/statusbar.png',
                               background_color=[.94, .94, .94, 1],
                               size=[50, 20],
                               size_hint_max_x=150,
                               size_hint_max_y=30)
            self.chrom_comp.add_widget(self.btn)
            for i in v:
                # each key (parameter name) is appended with
                # the parameter value from each component
                for p, val in i.items():
                    if p not in parameters:
                        parameters[p] = [val]
                    else:
                        parameters[p] += [val]
        # creates the cell with parameter name
        for p in parameters.keys():
            self.btn_p = MyLabel(text=str(p),
                                 markup=True,
                                 background_normal='images/statusbar.png',
                                 background_down='images/statusbar.png',
                                 background_color=[.94, .94, .94, 1],
                                 size=[50, 20],
                                 size_hint_max_x=80,
                                 size_hint_max_y=30)        
            self.chrom_params.add_widget(self.btn_p)
            # creates the cells with values of params for each component
            for v in parameters[p]:        
                self.btn_v = MyLabel(text=str(v),
                                     background_normal='images/statusbar.png',
                                     background_down='images/statusbar.png',
                                     size=[50, 20],
                                     size_hint_max_x=150,
                                     size_hint_max_y=30)
                self.chrom_params.add_widget(self.btn_v)

    def statusbar(self, instance):
        # file name output to status bar and run graph
        if isinstance(instance, str):
            self.status_bar.text = os.path.basename(instance)
            self.gcrun(instance)
            self.params_table(instance)
        else:
            self.status_bar.text = instance.text
            self.gcrun(self.status_bar.text)
            self.params_table(self.status_bar.text)
        self.date_inj.text = ('Дата и время анализа: ' +
                              chrom.date_injection + ', ' +
                              chrom.time_injection)
    
    def gcrun(self, datafile):
        # displays or refresh graph setups from gc's data file
        self.plot.points = chrom.gchrom_sec(datafile)
        # refresh x, y-ranges values
        self.graph.ymin = chrom.ymin
        self.graph.ymax = chrom.ymax
        self.graph.xmax = chrom.xmax
        self.graph.y_ticks_major = (self.graph.ymax - self.graph.ymin) / 4

    def GC(self):
        # returns chromatography data in two-dimensional list
        return [[0, 0], [0, 0]]
    
    def submit(self, *args):
        # checks the submit file for .txt ext.,
        # checks the file contents for GC data and
        # passes Path as an argument to the statusbar foo,
        ## or calls not_gc foo (file not contains GC data)
        # ignores submit if file doesn't have GC data
        try:
            if args[1][0].endswith('.txt'):
                with open(args[1][0], 'r') as inf:
                    for n, line in enumerate(inf, 1):
                        line = line.rstrip('\n')
                        # checks the file contents for GC data
                        if line.find('FID A, pA') != -1:
                            self.modal_open_file.dismiss()
                            self.statusbar(args[1][0])
                            
        except Exception:
            pass
            
    def screen_open_file(self, *args):
        self.manager.transition.direction = 'up'
        self.manager.current = 'openfile'
        

class MyChooser(FileChooserIconView):
    """Implementation of a :class:`FileChooserIconView`
    using different color scheme for filename and dirname

    """
    def __init__(self, **kwargs):
        super(MyChooser, self).__init__(**kwargs)
        Clock.schedule_once(self.init_widget, 0)

    def init_widget(self, *args):
        self.bind(on_entry_added=self.update_file_list_entry)
        self.bind(on_subentry_to_entry=self.update_file_list_entry)

    def update_file_list_entry(self, file_chooser, file_list_entry, *args):
        file_list_entry.children[0].color = (0.2, 0.2, 0.5, 1.0)
        file_list_entry.children[0].font_size = (10)
        file_list_entry.children[1].color = (0.0, 0.0, 0.0, 1.0)
        file_list_entry.children[1].font_size = (14)

class FileOpen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        bl = BoxLayout(orientation='vertical',
                       spacing=5,
                       padding=[10]
                       )

        button_choose_file = Button(text='Load file',
                                    background_color=[2, 1.5, 3, 1],
                                    size_hint=[1, .1],
                                    on_press=self.screen_open_file
                                    )

        bl.add_widget(button_choose_file)
        self.add_widget(bl)

    def screen_open_file(self, *args):
        self.manager.transition.direction = 'down'
        self.manager.current = 'main_screen'

class MyLabel(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    background_color = ColorProperty([.94, 1, .96, 1])
    background_normal = StringProperty('')
    background_down = StringProperty('')
    color = ColorProperty([0, 0, 0, 1])
    

class MyApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(ScreenMain(name='main_screen'))
        sm.add_widget(FileOpen(name='openfile'))

        # background setups
        Window.bind(on_resize=self.resize)
        with Window.canvas:
            Color(.94, 1, .96, 1)
            self.rect = Rectangle(size=[Window.size[0], Window.size[1]])
        return sm

    def resize(self, instance, width, height):
        self.rect.size = [width, height]


if __name__ == "__main__":                    
    MyApp().run()


