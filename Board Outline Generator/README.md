# KiCAD Board Outline Generator Plugin

A KiCAD action plugin that automates the creation of board outlines with rounded corners and mounting holes.

## Features

- **Configurable board dimensions** (width × height in mm)
- **Rounded corners** with adjustable radius
- **Mounting hole placement** with visual position editor
- **Preset fastener sizes** for common hardware:
  - Metric: M2, M2.5, M3, M4, M5, M6
  - Imperial: #4-40, #6-32, #8-32, #10-32, 1/4-20, 5/16-18
- **Custom hole diameter** for non-standard sizes
- **One-click corner hole placement** with configurable inset

## Installation

Copy `board_outline_generator.py` to your KiCAD plugins folder:

| OS      | Path                                                        |
|---------|-------------------------------------------------------------|
| Windows | `%APPDATA%\kicad\<version>\scripting\plugins\`              |
| Linux   | `~/.local/share/kicad/<version>/scripting/plugins/`         |
| macOS   | `~/Library/Preferences/kicad/<version>/scripting/plugins/`  |

Then in KiCAD PCB Editor:
1. Go to **Tools → External Plugins → Refresh Plugins**
2. The plugin will appear in **Tools → External Plugins → Board Outline Generator**

## Usage

1. Open a PCB file (or create a new one)
2. Run the plugin from **Tools → External Plugins → Board Outline Generator**
3. Configure your board:

### Board Dimensions
- **Width (X)**: Board width in mm
- **Height (Y)**: Board height in mm  
- **Corner Radius**: Radius for rounded corners (0 for sharp corners)

### Mounting Hole Size
- **Fastener Preset**: Select a common fastener size to auto-fill the hole diameter
- **Hole Diameter**: Direct entry for custom sizes (clearance hole diameter)
- **Annular Ring**: Copper ring width around the hole (for soldermask clearance)

### Mounting Hole Positions
- **Add Hole**: Manually add a hole with X/Y coordinates
- **Add 4 Corner Holes**: Automatically places holes at all four corners
- **Corner Inset**: Distance from board edge for corner hole placement
- **Clear All**: Remove all hole entries

### Coordinate System
- Origin (0, 0) is at the **top-left** corner of the board
- X increases to the right
- Y increases downward
- The board is automatically placed 25mm from the sheet origin so it appears within the default KiCAD sheet border

## Example

To create a 100mm × 80mm board with M3 mounting holes at each corner, 5mm from the edges:

1. Set Width: `100`, Height: `80`, Corner Radius: `3`
2. Select Fastener Preset: `M3` (auto-fills 3.4mm diameter)
3. Set Corner Inset: `5`
4. Click **Add 4 Corner Holes**
5. Click **Generate**

## Clearance Hole Reference

| Fastener | Clearance Hole (mm) |
|----------|---------------------|
| M2       | 2.4                 |
| M2.5     | 2.9                 |
| M3       | 3.4                 |
| M4       | 4.5                 |
| M5       | 5.5                 |
| M6       | 6.6                 |
| #4-40    | 3.3                 |
| #6-32    | 3.8                 |
| #8-32    | 4.5                 |
| #10-32   | 5.1                 |
| 1/4-20   | 6.6                 |
| 5/16-18  | 8.4                 |

## Notes

- The plugin creates **NPTH (Non-Plated Through Holes)** for mounting holes
- Board outline is drawn on the **Edge.Cuts** layer
- Mounting holes are added as footprints with reference designators (H1, H2, etc.)
- You can move/edit the generated geometry after creation using normal KiCAD tools

## Troubleshooting

**Plugin doesn't appear in menu:**
- Make sure the file is in the correct plugins folder for your KiCAD version
- Try restarting KiCAD completely
- Check the scripting console for error messages

**Arcs look wrong:**
- This can happen with very small corner radii; try increasing the radius

**Holes in wrong position:**
- Remember that Y=0 is at the top of the board, and Y increases downward (matching KiCAD's native coordinate system)
