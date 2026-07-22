// ============================================================
// MP60 dry-side catch bracket ("safety basket") -- v2, arched windows
//
// Glues to the UNDERSIDE of the tank's bottom glass with 20kg
// double-sided tape. Job: if the magnetic coupling ever releases,
// the dry side drops 3mm onto the ledge instead of into the sump.
//
// Design rules:
//  * NEVER touches the dry side in normal operation (2.5mm radial
//    clearance past the rubber shim): zero vibration coupling, the
//    magnetic seating and shim do their job undisturbed.
//  * Venting: 4 big gothic-arched windows + the open mouth expose
//    most of the air-cooled housing. Arched tops = self-supporting.
//  * C-shape, 130 deg mouth: dry side slides out sideways for
//    service without peeling the tape. INSTALL with the mouth
//    pointing the SAME direction as the fan exit (thrust reaction
//    pushes the pump into the closed back of the C).
//  * Print PADS-DOWN on the textured sheet: tape face comes out
//    dead flat. No supports needed anywhere.
//
// MEASURE FIRST (calliper the dry side):
DRY_OD     = 103;  // dry side housing diameter (spec ~102)
DRY_H      = 72;   // glass face -> bottom of dry side, incl. shim
SHIM_EXTRA = 6;    // how much the rubber shim adds to the diameter
// ------------------------------------------------------------
CLEAR     = 2.5;   // radial clearance past the shim
DROP_GAP  = 3;     // ledge sits this far below the dry side
WALL      = 4;
LEDGE_W   = 11;    // ledge reach inward under the housing
LEDGE_T   = 5;
PAD_L     = 42;    // tape pad, radial
PAD_W     = 38;    // tape pad, tangential
TOP_BAND  = 9;     // solid band at the tape plane
MOUTH_DEG = 130;

ID     = DRY_OD + SHIM_EXTRA + 2*CLEAR;
R_IN   = ID/2;
R_OUT  = R_IN + WALL;
H_COL  = DRY_H + DROP_GAP;         // tape plane -> catch face
H_TOT  = H_COL + LEDGE_T;
C_A0   = MOUTH_DEG/2;              // C spans C_A0 .. 360-C_A0, mouth on +X
C_SPAN = 360 - MOUTH_DEG;
RIBS   = [for (i = [0:4]) C_A0 + i*C_SPAN/4];   // 5 rib centers
PADS   = [RIBS[1], RIBS[2], RIBS[3]];
WIN_H0 = TOP_BAND;                 // window bottom (print z)
WIN_H1 = H_COL - 10;               // window arch apex
$fn = 160;

module c_shell() {
    rotate([0, 0, C_A0]) rotate_extrude(angle = C_SPAN)
        translate([R_IN, 0]) square([WALL, H_TOT]);
}

module ledge() {
    // catch ring + 45deg chamfer, both riding on the full shell
    rotate([0, 0, C_A0]) rotate_extrude(angle = C_SPAN) union() {
        translate([R_IN - LEDGE_W, H_COL]) square([WALL + LEDGE_W, LEDGE_T]);
        polygon([[R_IN, H_COL], [R_IN - LEDGE_W, H_COL],
                 [R_IN, H_COL - LEDGE_W]]);
    }
}

module window_cutter(ang) {
    // chordal prism with a 45deg pointed-arch top, pushed through the wall
    win_w = 2 * R_IN * sin((C_SPAN/4 - 9)/2);      // leaves ~9deg ribs
    rise  = min(win_w/2, WIN_H1 - WIN_H0 - 10);
    rotate([0, 0, ang]) translate([(R_IN + R_OUT)/2, 0, 0])
        rotate([90, 0, 90]) translate([0, 0, -WALL*2]) linear_extrude(WALL*4)
            polygon([[-win_w/2, WIN_H0], [win_w/2, WIN_H0],
                     [win_w/2, WIN_H1 - rise], [0, WIN_H1],
                     [-win_w/2, WIN_H1 - rise]]);
}

module pad(ang) {
    rotate([0, 0, ang]) {
        translate([R_IN, -PAD_W/2, 0]) cube([WALL + PAD_L, PAD_W, WALL]);
        hull() {   // 45deg gusset, prints pads-down with no support
            translate([R_OUT - 0.1, -PAD_W/4, 0])
                cube([0.1, PAD_W/2, WALL + 26]);
            translate([R_OUT + PAD_L - 8, -PAD_W/4, 0])
                cube([8, PAD_W/2, WALL]);
        }
    }
}

difference() {
    union() {
        c_shell();
        ledge();
        for (a = PADS) pad(a);
    }
    for (i = [0:3]) window_cutter(C_A0 + (i + 0.5) * C_SPAN/4);
}
