"""One graph for main/splitter, with an explicit choice of editable controls."""
import pyqtgraph as pg
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QTabWidget,QWidget,QVBoxLayout,QLabel,QPushButton,QStackedWidget,QHBoxLayout
from .profile_distribution_editor import ProfileDistributionEditor
from .plot_fitting import install_plot_fit


class CombinedProfileEditor(ProfileDistributionEditor):
    editSplitterRequested=Signal()

    def __init__(self,kind):
        self._legend_prefix='Main ';self.peer=None;self.comparison=False;self.independent=False
        self.references={};self._mode_key=None
        super().__init__(kind)
        self.layout_main.removeWidget(self.scroll)
        self.groups=QTabWidget();self.groups.addTab(self.scroll,'主翼 / Main')
        self.splitter_page=QStackedWidget()
        linked=QWidget();layout=QVBoxLayout(linked)
        note=QLabel('主翼連動中です。専用の角度・厚さを編集するには主翼からコピーします。');note.setWordWrap(True)
        layout.addWidget(note);button=QPushButton('主翼からコピーしてスプリッターを編集')
        button.clicked.connect(lambda *_:self.editSplitterRequested.emit());layout.addWidget(button);layout.addStretch()
        self.splitter_page.addWidget(linked);self.linked_page=linked
        self.groups.addTab(self.splitter_page,'スプリッター / Splitter');self.groups.setTabVisible(1,False)
        self.layout_main.addWidget(self.groups,1)
        toolbar=QHBoxLayout();toolbar.addStretch();fit=QPushButton('全体表示 / Fit')
        fit.clicked.connect(lambda *_:install_plot_fit(self.plot).request());toolbar.addWidget(fit)
        self.layout_main.insertLayout(0,toolbar)
        self.groups.currentChanged.connect(self.refresh_controls)
        self.scroll.setMinimumHeight(0)

    def attach_peer(self,peer):
        if self.peer is peer:return
        self.peer=peer;old=peer.plot
        peer._legend_prefix='Splitter ';peer._shared_host=self
        for span,editor in peer.series.items():
            peer.legend.removeItem(editor.curve)
            for item in (editor.curve,editor.handles):old.removeItem(item);self.plot.addItem(item)
            editor.plot=self.plot
            self.legend.addItem(editor.curve,'Splitter '+peer._profile_labels[span])
        peer.layout_main.removeWidget(old);old.hide();old.deleteLater()
        peer.plot=self.plot;peer.legend=self.legend
        self.splitter_page.addWidget(peer.scroll);peer.scroll.setMinimumHeight(0)

    def set_splitter(self,sections,settings,peer=None):
        enabled=bool(sections);independent=enabled and peer is not None
        if peer is not None:self.attach_peer(peer)
        self.comparison=enabled;self.independent=independent
        self.groups.setTabVisible(1,enabled)
        if not enabled:self.groups.setCurrentIndex(0)
        self.groups.setTabText(0,'主翼 / Main' if enabled else '編集 / Profiles')
        self.splitter_page.setCurrentWidget(self.peer.scroll if independent else self.linked_page)
        desired={section.span for section in sections or []} if enabled and not independent else set()
        for span,curve in list(self.references.items()):
            if span not in desired:
                self.legend.removeItem(curve);self.plot.removeItem(curve);del self.references[span]
        for section in sections or []:
            if independent:break
            span=section.span
            if span not in self.references:
                name='Hub' if span==0 else 'Tip' if span==1 else f'Span {span:.6g}'
                self.references[span]=self.plot.plot(name='Splitter '+name+' (linked)',pen=pg.mkPen('#8deb87' if span!=1 else '#e5a5f5',width=2,style=Qt.PenStyle.DashDotLine))
            start=(1-span)*settings.hub_start_fraction+span*settings.tip_start_fraction
            values=section.beta_m_deg if self.kind=='blade_angle' else section.thickness/settings.thickness_scale
            self.references[span].setData(start+(1-start)*section.camber.m_blade_norm,values)
        key=(enabled,independent,tuple(desired),tuple(self.series),tuple(peer.series) if peer is not None else ())
        self.refresh_controls()
        if key!=self._mode_key:install_plot_fit(self.plot).request()
        self._mode_key=key

    def refresh_controls(self,*_):
        if not hasattr(self,'groups'):return
        selected=self.groups.currentIndex()
        for span,editor in self.series.items():
            editor.handles.setVisible(selected==0)
            label=self.legend.getLabel(editor.curve)
            if label is not None:label.setText(('Main ' if self.comparison else '')+self._profile_labels[span])
        if self.peer is not None:
            for span,editor in self.peer.series.items():
                color='#e5a5f5' if span==1 else '#8deb87'
                editor.curve.setPen(pg.mkPen(color,width=2,style=Qt.PenStyle.DashDotLine))
                editor.curve.setVisible(self.independent)
                editor.handles.color=color;editor.handles.symbol='t';editor.handles.point_size=15
                editor.handles.set_points(editor._points);editor.handles.setVisible(self.independent and selected==1)
                label=self.legend.getLabel(editor.curve)
                if self.independent and label is None:self.legend.addItem(editor.curve,'Splitter '+self.peer._profile_labels[span])
                elif not self.independent and label is not None:self.legend.removeItem(editor.curve)
        self.hint.setText(('主翼とスプリッターを比較表示。下のタブで編集対象を選択。Splitterは緑／紫の一点鎖線・三角点。'
                           +(' 厚さは倍率適用前です。' if self.kind=='thickness' else '')) if self.comparison else 'Hub / Tipの点をドラッグ、または表で編集します。')
        if self.sender() is self.groups:install_plot_fit(self.plot).request()
