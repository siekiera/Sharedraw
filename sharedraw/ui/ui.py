import io
from tkinter import *
from PIL import Image, ImageDraw
from sharedraw.ui.messages import ImageMessage
from sharedraw.ui.networking import PeerPool

__author__ = 'michalek'

WIDTH, HEIGHT = 640, 480


class SharedrawUI():
    def __init__(self, peer_pool: PeerPool):
        self.root = Tk()
        self.peer_pool = peer_pool
        self.ui = MainFrame(self)

    def start(self):
        # self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.mainloop()

    def get_png(self):
        return self.ui.drawer.as_png()

    def connect(self, ip, port):
        self.peer_pool.connect_to(ip, int(port))


class MainFrame(Frame):
    def __init__(self, ui: SharedrawUI):
        Frame.__init__(self, ui.root)
        self.parent = ui.root
        self.ui = ui
        self.init()
        # self.c = None

    def init(self):
        self.parent.title("Sharedraw [localhost:%s]" % self.ui.peer_pool.port)
        self.drawer = Drawer(self.parent, WIDTH, HEIGHT)
        self.b = Button(self.parent, text="Zapisz")
        self.b.pack()
        self.b.bind("<Button-1>", self.save)
        connect_btn = Button(self.parent, text="Podłącz")
        connect_btn.pack()
        connect_btn.bind("<Button-1>", self.connect)

    def save(self, e):
        # png = self.drawer.as_png()
        msg = ImageMessage(self.drawer.changed_pxs)
        self.ui.peer_pool.send(msg)

    def connect(self, e):
        d = ConnectDialog(self.ui)
        self.parent.wait_window(d.top)


class Drawer():
    x, y = None, None

    def __init__(self, parent, width, height):
        self.c = Canvas(parent, width=width, height=height, bg="white")
        self.c.pack()
        # TODO - to można wywalić raczej
        self.img = Image.new("RGB", (width, height), (255, 255, 255))
        self.img_draw = ImageDraw.Draw(self.img)
        self.c.bind("<B1-Motion>", self.motion)
        self.c.bind("<ButtonRelease-1>", self.release)
        self.changed_pxs = []

    def motion(self, e):
        prevx = self.x if self.x is not None else e.x
        prevy = self.y if self.y is not None else e.y
        self.c.create_line(prevx, prevy, e.x, e.y)
        self.img_draw.line([prevx, prevy, e.x, e.y])
        self.x = e.x
        self.y = e.y
        self.changed_pxs.append((e.x, e.y))
        print('e (%s,%s)' % (e.x, e.y))
        print('self (%s,%s)' % (self.x, self.y))

    def release(self, e):
        self.x = None
        self.y = None

    def as_png(self):
        imgbytearr = io.BytesIO()
        self.img.save(imgbytearr, format='PNG')
        return imgbytearr.getvalue()


class ConnectDialog:
    def __init__(self, ui: SharedrawUI):
        top = self.top = Toplevel(ui.root)
        self.ui = ui
        Label(top, text="IP").pack()
        self.ip_entry = Entry(top)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack()
        Label(top, text="Port").pack()
        self.port_entry = Entry(top)
        self.port_entry.insert(0, "12345")
        self.port_entry.pack()

        b = Button(top, text="Połącz", command=self.connect)
        b.pack()

    def connect(self):
        self.ui.connect(self.ip_entry.get(), self.port_entry.get())
        self.top.destroy()