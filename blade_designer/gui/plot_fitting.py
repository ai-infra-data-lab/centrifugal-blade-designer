"""Fit on presentation, after Qt lays out the plot; leave editing zoom alone."""
from PySide6.QtCore import QObject,QEvent,QTimer
import pyqtgraph as pg


class PlotPresentationFit(QObject):
    def __init__(self,plot):
        super().__init__(plot);self.plot=plot;self.pending=False
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.fit)
        plot.installEventFilter(self)

    def request(self):
        if not self.pending:
            self.pending=True;self.timer.start(0)

    def fit(self):
        self.pending=False
        if self.plot.isVisible():
            self.plot.autoRange(padding=.06);self.plot.disableAutoRange()

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.Show:self.request()
        return False


def install_plot_fit(plot):
    if not hasattr(plot,'_presentation_fit'):plot._presentation_fit=PlotPresentationFit(plot)
    return plot._presentation_fit


def fit_visible_plots(widget):
    plots=([widget] if isinstance(widget,pg.PlotWidget) else [])+widget.findChildren(pg.PlotWidget)
    for plot in plots:
        if plot.isVisible():install_plot_fit(plot).request()
