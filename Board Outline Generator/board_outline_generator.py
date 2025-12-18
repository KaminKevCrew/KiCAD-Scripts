"""
KiCAD Board Outline and Mounting Hole Generator Plugin
=======================================================
Creates board outlines with rounded corners and places mounting holes.

Installation:
    Copy this file to your KiCAD plugins folder:
    - Windows: %APPDATA%/kicad/<version>/scripting/plugins/
    - Linux: ~/.local/share/kicad/<version>/scripting/plugins/
    - macOS: ~/Library/Preferences/kicad/<version>/scripting/plugins/
    
    Then refresh plugins in KiCAD: Tools -> External Plugins -> Refresh Plugins
"""

import pcbnew
import wx
import math

# Board placement offset from sheet origin (mm)
# This positions the board within the default KiCAD sheet border
BOARD_OFFSET_X = 25.0
BOARD_OFFSET_Y = 25.0

# Clearance hole sizes (diameter in mm) for common fasteners
# Using "close fit" clearance holes per standard tables
CLEARANCE_HOLES = {
    "M2":       2.4,
    "M2.5":     2.9,
    "M3":       3.4,
    "M4":       4.5,
    "M5":       5.5,
    "M6":       6.6,
    "#4-40":    3.3,
    "#6-32":    3.8,
    "#8-32":    4.5,
    "#10-32":   5.1,
    "1/4-20":   6.6,
    "5/16-18":  8.4,
}


class MountingHoleEntry(wx.Panel):
    """Panel for entering a single mounting hole position."""
    
    def __init__(self, parent, index, on_remove_callback):
        super().__init__(parent)
        self.index = index
        self.on_remove = on_remove_callback
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        label = wx.StaticText(self, label=f"Hole {index + 1}:")
        label.SetMinSize((50, -1))
        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        sizer.Add(wx.StaticText(self, label="X:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 2)
        self.x_ctrl = wx.TextCtrl(self, size=(60, -1), value="3.5")
        sizer.Add(self.x_ctrl, 0, wx.RIGHT, 10)
        
        sizer.Add(wx.StaticText(self, label="Y:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 2)
        self.y_ctrl = wx.TextCtrl(self, size=(60, -1), value="3.5")
        sizer.Add(self.y_ctrl, 0, wx.RIGHT, 10)
        
        remove_btn = wx.Button(self, label="Remove", size=(60, -1))
        remove_btn.Bind(wx.EVT_BUTTON, self._on_remove)
        sizer.Add(remove_btn, 0)
        
        self.SetSizer(sizer)
    
    def _on_remove(self, event):
        self.on_remove(self)
    
    def get_position(self):
        """Returns (x, y) tuple in mm, or None if invalid."""
        try:
            x = float(self.x_ctrl.GetValue())
            y = float(self.y_ctrl.GetValue())
            return (x, y)
        except ValueError:
            return None


class BoardOutlineDialog(wx.Dialog):
    """Main dialog for board outline and mounting hole configuration."""
    
    def __init__(self, parent):
        super().__init__(parent, title="Board Outline Generator", 
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        self.hole_entries = []
        self._build_ui()
        self.SetMinSize((500, 600))
        self.Fit()
        self.Centre()
    
    def _build_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Board Dimensions Section
        dim_box = wx.StaticBox(self, label="Board Dimensions (mm)")
        dim_sizer = wx.StaticBoxSizer(dim_box, wx.VERTICAL)
        
        grid = wx.FlexGridSizer(3, 2, 8, 15)
        
        grid.Add(wx.StaticText(self, label="Width (X):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.width_ctrl = wx.TextCtrl(self, value="100")
        grid.Add(self.width_ctrl, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(self, label="Height (Y):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.height_ctrl = wx.TextCtrl(self, value="80")
        grid.Add(self.height_ctrl, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(self, label="Corner Radius:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.radius_ctrl = wx.TextCtrl(self, value="3")
        grid.Add(self.radius_ctrl, 1, wx.EXPAND)
        
        grid.AddGrowableCol(1, 1)
        dim_sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(dim_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Mounting Hole Size Section
        hole_size_box = wx.StaticBox(self, label="Mounting Hole Size")
        hole_size_sizer = wx.StaticBoxSizer(hole_size_box, wx.VERTICAL)
        
        # Preset selector
        preset_sizer = wx.BoxSizer(wx.HORIZONTAL)
        preset_sizer.Add(wx.StaticText(self, label="Fastener Preset:"), 
                         0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        
        self.preset_choice = wx.Choice(self, choices=["Custom"] + list(CLEARANCE_HOLES.keys()))
        self.preset_choice.SetSelection(0)
        self.preset_choice.Bind(wx.EVT_CHOICE, self._on_preset_changed)
        preset_sizer.Add(self.preset_choice, 1)
        hole_size_sizer.Add(preset_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Direct entry
        direct_sizer = wx.BoxSizer(wx.HORIZONTAL)
        direct_sizer.Add(wx.StaticText(self, label="Hole Diameter (mm):"), 
                         0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.hole_diameter_ctrl = wx.TextCtrl(self, value="3.4")
        direct_sizer.Add(self.hole_diameter_ctrl, 1)
        hole_size_sizer.Add(direct_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # Annular ring (pad size)
        ring_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ring_sizer.Add(wx.StaticText(self, label="Annular Ring (mm):"), 
                       0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.annular_ring_ctrl = wx.TextCtrl(self, value="1.0")
        ring_sizer.Add(self.annular_ring_ctrl, 1)
        hole_size_sizer.Add(ring_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        main_sizer.Add(hole_size_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Mounting Hole Positions Section
        positions_box = wx.StaticBox(self, label="Mounting Hole Positions (mm from top-left)")
        positions_sizer = wx.StaticBoxSizer(positions_box, wx.VERTICAL)
        
        # Scrolled panel for hole entries
        self.holes_panel = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.holes_panel.SetScrollRate(0, 20)
        self.holes_sizer = wx.BoxSizer(wx.VERTICAL)
        self.holes_panel.SetSizer(self.holes_sizer)
        self.holes_panel.SetMinSize((-1, 150))
        
        positions_sizer.Add(self.holes_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        # Add hole button and corner preset
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        add_btn = wx.Button(self, label="Add Hole")
        add_btn.Bind(wx.EVT_BUTTON, self._on_add_hole)
        btn_sizer.Add(add_btn, 0, wx.RIGHT, 10)
        
        corners_btn = wx.Button(self, label="Add 4 Corner Holes")
        corners_btn.Bind(wx.EVT_BUTTON, self._on_add_corners)
        btn_sizer.Add(corners_btn, 0, wx.RIGHT, 10)
        
        clear_btn = wx.Button(self, label="Clear All")
        clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_holes)
        btn_sizer.Add(clear_btn, 0)
        
        positions_sizer.Add(btn_sizer, 0, wx.ALL, 10)
        
        # Inset control for corner holes
        inset_sizer = wx.BoxSizer(wx.HORIZONTAL)
        inset_sizer.Add(wx.StaticText(self, label="Corner Inset (for presets):"), 
                        0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.inset_ctrl = wx.TextCtrl(self, value="5.0")
        inset_sizer.Add(self.inset_ctrl, 0)
        inset_sizer.Add(wx.StaticText(self, label="mm"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        positions_sizer.Add(inset_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        main_sizer.Add(positions_sizer, 1, wx.EXPAND | wx.ALL, 10)
        
        # Dialog buttons
        btn_sizer = wx.StdDialogButtonSizer()
        
        ok_btn = wx.Button(self, wx.ID_OK, "Generate")
        ok_btn.SetDefault()
        btn_sizer.AddButton(ok_btn)
        
        cancel_btn = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(cancel_btn)
        
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
    
    def _on_preset_changed(self, event):
        selection = self.preset_choice.GetStringSelection()
        if selection in CLEARANCE_HOLES:
            self.hole_diameter_ctrl.SetValue(str(CLEARANCE_HOLES[selection]))
    
    def _on_add_hole(self, event):
        self._add_hole_entry()
    
    def _add_hole_entry(self, x="3.5", y="3.5"):
        entry = MountingHoleEntry(self.holes_panel, len(self.hole_entries), 
                                   self._remove_hole_entry)
        entry.x_ctrl.SetValue(str(x))
        entry.y_ctrl.SetValue(str(y))
        self.hole_entries.append(entry)
        self.holes_sizer.Add(entry, 0, wx.EXPAND | wx.ALL, 2)
        self.holes_panel.FitInside()
        self.holes_panel.Layout()
    
    def _remove_hole_entry(self, entry):
        self.hole_entries.remove(entry)
        entry.Destroy()
        # Renumber remaining entries
        for i, e in enumerate(self.hole_entries):
            e.index = i
        self.holes_panel.FitInside()
        self.holes_panel.Layout()
    
    def _on_add_corners(self, event):
        """Add 4 mounting holes at the corners with specified inset."""
        try:
            width = float(self.width_ctrl.GetValue())
            height = float(self.height_ctrl.GetValue())
            inset = float(self.inset_ctrl.GetValue())
        except ValueError:
            wx.MessageBox("Please enter valid board dimensions first.", 
                          "Invalid Input", wx.OK | wx.ICON_ERROR)
            return
        
        # Add holes at four corners (origin at top-left)
        corners = [
            (inset, inset),                    # Top-left
            (width - inset, inset),            # Top-right
            (inset, height - inset),           # Bottom-left
            (width - inset, height - inset),   # Bottom-right
        ]
        
        for x, y in corners:
            self._add_hole_entry(x, y)
    
    def _on_clear_holes(self, event):
        for entry in self.hole_entries[:]:
            entry.Destroy()
        self.hole_entries.clear()
        self.holes_panel.FitInside()
        self.holes_panel.Layout()
    
    def get_parameters(self):
        """Returns dict of all parameters, or None if validation fails."""
        try:
            params = {
                'width': float(self.width_ctrl.GetValue()),
                'height': float(self.height_ctrl.GetValue()),
                'corner_radius': float(self.radius_ctrl.GetValue()),
                'hole_diameter': float(self.hole_diameter_ctrl.GetValue()),
                'annular_ring': float(self.annular_ring_ctrl.GetValue()),
                'hole_positions': []
            }
            
            for entry in self.hole_entries:
                pos = entry.get_position()
                if pos is None:
                    raise ValueError(f"Invalid position for hole {entry.index + 1}")
                params['hole_positions'].append(pos)
            
            # Validation
            if params['width'] <= 0 or params['height'] <= 0:
                raise ValueError("Board dimensions must be positive")
            if params['corner_radius'] < 0:
                raise ValueError("Corner radius cannot be negative")
            if params['corner_radius'] > min(params['width'], params['height']) / 2:
                raise ValueError("Corner radius too large for board size")
            if params['hole_diameter'] <= 0:
                raise ValueError("Hole diameter must be positive")
            
            return params
            
        except ValueError as e:
            wx.MessageBox(str(e), "Invalid Input", wx.OK | wx.ICON_ERROR)
            return None


def create_board_outline(board, width, height, corner_radius):
    """
    Creates a board outline on the Edge.Cuts layer.
    
    Coordinate system:
    - Origin (0,0) is at the TOP-LEFT corner of the board
    - X increases to the right
    - Y increases downward (matching KiCAD's native coordinate system)
    
    The board is offset from the sheet origin by BOARD_OFFSET_X/Y so it
    appears within the default sheet border.
    """
    # KiCAD uses nanometers internally
    def mm_to_nm(mm):
        return int(mm * 1e6)
    
    edge_cuts = board.GetLayerID("Edge.Cuts")
    
    # Apply offset so board appears within sheet border
    ox = BOARD_OFFSET_X
    oy = BOARD_OFFSET_Y
    
    r = corner_radius
    w = width
    h = height
    
    if r == 0:
        # Simple rectangle - no rounded corners
        points = [
            (ox, oy),
            (ox + w, oy),
            (ox + w, oy + h),
            (ox, oy + h),
            (ox, oy)  # Close the shape
        ]
        
        for i in range(len(points) - 1):
            line = pcbnew.PCB_SHAPE(board)
            line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetLayer(edge_cuts)
            line.SetStart(pcbnew.VECTOR2I(mm_to_nm(points[i][0]), mm_to_nm(points[i][1])))
            line.SetEnd(pcbnew.VECTOR2I(mm_to_nm(points[i+1][0]), mm_to_nm(points[i+1][1])))
            line.SetWidth(mm_to_nm(0.1))
            board.Add(line)
    else:
        # Rounded rectangle
        # We need 4 arcs at corners and 4 lines connecting them
        
        # Corner centers (with offset applied)
        corners = [
            (ox + r, oy + r),              # Top-left
            (ox + w - r, oy + r),          # Top-right  
            (ox + w - r, oy + h - r),      # Bottom-right
            (ox + r, oy + h - r),          # Bottom-left
        ]
        
        # Lines connecting the arcs
        lines = [
            ((ox + r, oy), (ox + w - r, oy)),               # Top edge
            ((ox + w, oy + r), (ox + w, oy + h - r)),       # Right edge
            ((ox + w - r, oy + h), (ox + r, oy + h)),       # Bottom edge
            ((ox, oy + h - r), (ox, oy + r)),               # Left edge
        ]
        
        for start, end in lines:
            line = pcbnew.PCB_SHAPE(board)
            line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetLayer(edge_cuts)
            line.SetStart(pcbnew.VECTOR2I(mm_to_nm(start[0]), mm_to_nm(start[1])))
            line.SetEnd(pcbnew.VECTOR2I(mm_to_nm(end[0]), mm_to_nm(end[1])))
            line.SetWidth(mm_to_nm(0.1))
            board.Add(line)
        
        # Arcs at corners
        # Using SetArcGeometry(start, mid, end) for reliable arc creation
        def create_arc(center, start_angle_deg, end_angle_deg):
            """Create an arc. Angles in degrees, 0 = right, increases counterclockwise."""
            cx, cy = center
            
            start_angle = math.radians(start_angle_deg)
            end_angle = math.radians(end_angle_deg)
            mid_angle = (start_angle + end_angle) / 2
            
            # In KiCAD, Y increases downward, so we negate the sin component
            start_pt = (cx + r * math.cos(start_angle), cy - r * math.sin(start_angle))
            mid_pt = (cx + r * math.cos(mid_angle), cy - r * math.sin(mid_angle))
            end_pt = (cx + r * math.cos(end_angle), cy - r * math.sin(end_angle))
            
            arc = pcbnew.PCB_SHAPE(board)
            arc.SetShape(pcbnew.SHAPE_T_ARC)
            arc.SetLayer(edge_cuts)
            arc.SetArcGeometry(
                pcbnew.VECTOR2I(mm_to_nm(start_pt[0]), mm_to_nm(start_pt[1])),
                pcbnew.VECTOR2I(mm_to_nm(mid_pt[0]), mm_to_nm(mid_pt[1])),
                pcbnew.VECTOR2I(mm_to_nm(end_pt[0]), mm_to_nm(end_pt[1]))
            )
            arc.SetWidth(mm_to_nm(0.1))
            board.Add(arc)
        
        # Top-left corner: arc from 90° to 180°
        create_arc(corners[0], 90, 180)
        # Top-right corner: arc from 0° to 90°
        create_arc(corners[1], 0, 90)
        # Bottom-right corner: arc from 270° to 360°
        create_arc(corners[2], 270, 360)
        # Bottom-left corner: arc from 180° to 270°
        create_arc(corners[3], 180, 270)


def create_mounting_hole(board, x, y, hole_diameter, annular_ring):
    """
    Creates a mounting hole footprint at the specified position.
    
    Position is in mm relative to the board's top-left corner.
    The board offset is applied automatically.
    """
    def mm_to_nm(mm):
        return int(mm * 1e6)
    
    pad_diameter = hole_diameter + (2 * annular_ring)
    
    # Create a footprint for the mounting hole
    footprint = pcbnew.FOOTPRINT(board)
    footprint.SetReference(f"H{len([f for f in board.GetFootprints() if f.GetReference().startswith('H')]) + 1}")
    footprint.SetValue("MountingHole")
    
    # Create the pad (NPTH - Non-Plated Through Hole for simple mounting holes)
    pad = pcbnew.PAD(footprint)
    pad.SetNumber("1")
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)  # Non-plated through hole
    pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE)
    pad.SetDrillSize(pcbnew.VECTOR2I(mm_to_nm(hole_diameter), mm_to_nm(hole_diameter)))
    pad.SetSize(pcbnew.VECTOR2I(mm_to_nm(hole_diameter), mm_to_nm(hole_diameter)))
    pad.SetPosition(pcbnew.VECTOR2I(0, 0))
    
    # Add soldermask opening (optional, for clearance around hole)
    pad.SetLocalSolderMaskMargin(mm_to_nm(annular_ring))
    
    footprint.Add(pad)
    
    # Position the footprint with board offset applied
    sheet_x = BOARD_OFFSET_X + x
    sheet_y = BOARD_OFFSET_Y + y
    footprint.SetPosition(pcbnew.VECTOR2I(mm_to_nm(sheet_x), mm_to_nm(sheet_y)))
    
    board.Add(footprint)
    return footprint


class BoardOutlinePlugin(pcbnew.ActionPlugin):
    """KiCAD Action Plugin for generating board outlines and mounting holes."""
    
    def defaults(self):
        self.name = "Board Outline Generator"
        self.category = "Board Setup"
        self.description = "Generate board outline with rounded corners and mounting holes"
        self.show_toolbar_button = True
        self.icon_file_name = ""  # Optional: path to icon
    
    def Run(self):
        board = pcbnew.GetBoard()
        
        dlg = BoardOutlineDialog(None)
        
        if dlg.ShowModal() == wx.ID_OK:
            params = dlg.get_parameters()
            
            if params:
                # Create board outline
                create_board_outline(
                    board,
                    params['width'],
                    params['height'],
                    params['corner_radius']
                )
                
                # Create mounting holes
                for x, y in params['hole_positions']:
                    create_mounting_hole(
                        board,
                        x, y,
                        params['hole_diameter'],
                        params['annular_ring']
                    )
                
                # Refresh the view
                pcbnew.Refresh()
                
                wx.MessageBox(
                    f"Created board outline: {params['width']}mm x {params['height']}mm\n"
                    f"Corner radius: {params['corner_radius']}mm\n"
                    f"Mounting holes: {len(params['hole_positions'])}\n"
                    f"Board placed at offset ({BOARD_OFFSET_X}, {BOARD_OFFSET_Y})mm",
                    "Board Outline Generator",
                    wx.OK | wx.ICON_INFORMATION
                )
        
        dlg.Destroy()


# Register the plugin
BoardOutlinePlugin().register()


# For running as a standalone script in KiCAD's scripting console:
if __name__ == "__main__":
    # Check if running inside KiCAD
    try:
        board = pcbnew.GetBoard()
        if board:
            app = wx.App()
            dlg = BoardOutlineDialog(None)
            
            if dlg.ShowModal() == wx.ID_OK:
                params = dlg.get_parameters()
                
                if params:
                    create_board_outline(
                        board,
                        params['width'],
                        params['height'],
                        params['corner_radius']
                    )
                    
                    for x, y in params['hole_positions']:
                        create_mounting_hole(
                            board,
                            x, y,
                            params['hole_diameter'],
                            params['annular_ring']
                        )
                    
                    pcbnew.Refresh()
                    print(f"Created board: {params['width']}mm x {params['height']}mm")
                    print(f"Added {len(params['hole_positions'])} mounting holes")
            
            dlg.Destroy()
        else:
            print("No board open. Please open a PCB first.")
    except Exception as e:
        print(f"Error: {e}")
        print("Run this script from within KiCAD's PCB editor.")
