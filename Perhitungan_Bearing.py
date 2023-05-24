from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QWidgetAction

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .Perhitungan_Bearing_dialog import BearingDialog
import os.path

from math import pi
from datetime import datetime, timezone
from qgis.core import Qgis
from qgis.core import QgsDistanceArea, QgsPointXY
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransformContext
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
from .lib.draw_mono_line_map_tool import DrawMonoLineMapTool
from .magnetic_model import MagneticModel

def rad2deg(v):
	return v * 180 / pi

# Return the interactive measurements toolbox widget, if found.
def measurementsToolbox(iface):
	for action in iface.attributesToolBar().actions():
			if isinstance(action, QWidgetAction):
				first_action = action.defaultWidget().actions()[0]
				if first_action == iface.actionMeasure():
					return action.defaultWidget()

# Return the interactive measurements menu, if found.
def measurementsMenu(iface):
	for action in iface.viewMenu().actions():
			if action.menu():
				first_action = action.menu().actions()[0]
				if first_action == iface.actionMeasure():
					return action.menu()


class Bearing:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'Bearing_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Perhitungan Bearing')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

        self.iface = iface
        self.canvas = iface.mapCanvas()

        # Temporal navigation
        self.temporalController = iface.mapCanvas().temporalController()
		#self.temporalController.navigationModeChanged.connect(self.updateMeasurement)
        self.temporalController.updateTemporalRange.connect(self.updateMeasurement)

        self.rubberBand = DrawMonoLineMapTool(self.canvas)
        self.rubberBand.deactivated.connect(self.close)
        self.rubberBand.measurement.connect(self.updatePoints)

        self.geod = QgsDistanceArea()
        self.geod.setEllipsoid('EPSG:7030')
        self.geod.setSourceCrs(QgsCoordinateReferenceSystem('EPSG:4326'), QgsProject().instance().transformContext())
        
        QgsProject().instance().crsChanged.connect(self.changeCrs)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Bearing', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/perhitungan_bearing/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Perhitungan Bearing'),
            add_to_menu=False,
            add_to_toolbar=False,
            callback=self.run,
            parent=self.iface.mainWindow())
		
        # Add this action to the measurements toolbox
        toolbox = measurementsToolbox(self.iface)
        if toolbox:
            toolbox.addAction(self.actions[0])

		# Add this action to the measurements menu
        menu = measurementsMenu(self.iface)
        if menu:
              menu.addAction(self.actions[0])
        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        toolbox = measurementsToolbox(self.iface)
        if toolbox:
            toolbox.removeAction(self.actions[0])

        menu = measurementsMenu(self.iface)
        if menu:
              menu.removeAction(self.actions[0])
        
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Perhitungan Bearing'),
                action)
            self.iface.removeToolBarIcon(action)

        self.deactivate()


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = BearingDialog()
            self.dlg.reset.connect(self.deactivate)
            self.dlg.perhitungan_bearing_radioButton.toggled.connect(self.setPerhitunganBearing)
        
        self.setTransform()

        # show the dialog
        self.dlg.show()

        self.canvas.setMapTool(self.rubberBand)

        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass

        self.close()

    def deactivate(self):
        self.rubberBand.reset()

        self.startPoint = None
        self.endPoint = None

        if hasattr(self, 'dlg'):
            self.dlg.azimuth_doubleSpinBox.setValue(0)
            self.dlg.distance_doubleSpinBox.setValue(0)
            self.dlg.declination_doubleSpinBox.setPrefix("E ")
            self.dlg.declination_doubleSpinBox.setValue(0)
            self.dlg.declination_doubleSpinBox.setSuffix("°")

    def close(self):
         self.dlg.deactivate()
         self.dlg.hide()

    def setBearingMeasurementMode(self, active):
        self.magnetic_measurements = active
        suffix = "° M" if active else "° T"
        self.dlg.azimuth_doubleSpinBox.setSuffix(suffix)
        self.updateMeasurement()

    def updatePoints(self, startPoint, endPoint):
        self.startPoint = startPoint
        self.endPoint = endPoint
        self.updateMeasurement()

    def updateMeasurement(self):

        if self.startPoint and self.endPoint:

            if self.dlg.isHidden():
                self.dlg.show()

                ts = None
			# If temporal navigation is enabled, use the timestamp of
			# the beginning of current frame instead of the current timestamp.
            if self.temporalController.navigationMode() != 0:
				# We could of course do this as a one-liner, but Python…
                current_frame = self.temporalController.currentFrameNumber()
                dtrange = self.temporalController.dateTimeRangeForFrameNumber(current_frame)
                ts = dtrange.begin().toPyDateTime().replace(tzinfo=timezone.utc)

            start = self.transform(QgsPointXY(self.startPoint.x(), self.startPoint.y()))
            end = self.transform(QgsPointXY(self.endPoint.x(), self.endPoint.y()))
            α = self.geod.bearing(start, end)
            ρ = self.geod.measureLine(start, end)
            
            try:
                dec, ε = self.mm.value_at(start.x(), start.y(), ts=ts)

                if self.magnetic_measurements:
                    displayAngle = (rad2deg(α) - dec) % 360
                else:
                    displayAngle = rad2deg(α) % 360

                hemisphere = "E " if dec > 0 else "W "
                self.dlg.declination_doubleSpinBox.setPrefix(hemisphere)
                self.dlg.declination_doubleSpinBox.setValue(abs(dec))
                self.dlg.declination_doubleSpinBox.setSuffix(f"° ±{ε:.2f}")
                self.dlg.azimuth_doubleSpinBox.setValue(displayAngle)
                self.dlg.distance_doubleSpinBox.setValue(ρ)

            except ValueError:
                self.deactivate()
				# In theory, it could also be x or y out of range but not with
				# the current wmmdata.bin data.
                self.iface.messageBar().pushMessage(f"Magnetic bearing: epoch is out of range. Valid epochs are {self.mm.min_t} to {self.mm.max_t}", level=Qgis.Warning)

    def setTransform(self):
		# Set up the coordinate geodetic transformer
        instance = QgsProject.instance()
        srcCrs = instance.crs()
        dstCrs = QgsCoordinateReferenceSystem('EPSG:4326')
        self.transformer = QgsCoordinateTransform(srcCrs, dstCrs, instance)

    def transform(self, point):
        return self.transformer.transform(point)

    def changeCrs(self):
        self.setTransform()
        self.deactivate()
