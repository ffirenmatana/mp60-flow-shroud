// ============================================================
// MP60 90-degree quarter-fan flow shroud ("cobra fan")
// Bottom-mounted VorTech MP60, vertical discharge -> horizontal
// 90-degree-arc sheet aimed back down a peninsula tank.
//
// Fluid design intent:
//  * circular nozzle bore morphs to a wide flat rectangle THROUGH
//    the 90-degree bend (turning losses are lowest mid-morph)
//  * 2 concentric turning vanes keep flow attached on the inner wall
//  * fan section spreads the sheet across ~90 degrees of arc using
//    3 cambered splitter vanes (outer channels steered ~+/-45 deg)
//  * 3 inlet straightening fins kill propeller swirl so the fan
//    fills evenly
//  * exit area ~= 1.15x nozzle bore area -> no added back-pressure
//
// Print: 2 mirrored clamshell halves (part=1 / part=2), flat face
// down, no supports. Join with 1.75mm filament dowels + reef-safe
// CA gel. It lives underwater - it does not need to be watertight.
// Material: black PETG, 4+ perimeters.
// ============================================================

/* [Render] */
part = 0;            // 0=assembly preview, 1=half A (+Y), 2=half B (-Y)
show_cutaway = false; // assembly preview sliced open to show vanes

/* [Pump interface -- MEASURE YOUR WET SIDE FIRST] */
NOZZLE_OD = 96;      // OD of stock nozzle ring the socket slips over
NOZZLE_ID = 90;      // nozzle exit bore (sets all internal areas)
SOCKET_DEPTH = 22;   // how far the socket overlaps the nozzle

/* [Duct geometry] */
WALL     = 3.2;      // 4 perimeters @ 0.4mm
INLET_Z  = 30;       // socket + straightener zone height (bend starts here)
BEND_R   = 65;       // centerline turn radius of the elbow
DUCT_W   = 110;      // rectangle width at end of bend (horizontal, in plan)
DUCT_H   = 56;       // rectangle height at end of bend (vertical)
DUCT_CR  = 10;       // corner radius of that rectangle
FAN_LEN  = 70;       // length of the fan/diffuser section
EXIT_W   = 210;      // inner width of exit slot (arc chord)
EXIT_H   = 35;       // inner height of exit slot  <-- sheet thickness knob
                     //   25 = harder/faster sheet, more throw
                     //   45 = softer, more diffuse

/* [Vanes] */
VT = 1.8;               // vane thickness
BEND_VANE_R = [44, 68]; // turning vane radii (from bend center)
FAN_VANES = 4;          // cambered splitters (even count keeps them off the split seam)
STRAIGHTENERS = true;   // anti-swirl fins in the inlet

/* [Fasteners] */
SCREW_D  = 4.4;      // M4 nylon set screws (x4) clamp socket to nozzle
NUT_W    = 7.4;      // M4 square nut pocket width
NUT_T    = 2.8;      // M4 square nut pocket thickness
DOWEL_D  = 2.05;     // 1.75mm filament alignment dowels

$fn = 64;
EPS = 0.02;

// ---- derived ----
ZC       = INLET_Z + BEND_R;        // duct centerline height after bend
FLOOR_IN = ZC - DUCT_H/2;           // inner floor of fan (flat)
CEIL0_IN = ZC + DUCT_H/2;           // inner ceiling at fan start
CEIL1_IN = FLOOR_IN + EXIT_H;       // inner ceiling at exit
X_EXIT   = BEND_R + FAN_LEN;        // exit face plane
DWH      = (EXIT_W - DUCT_W)/2;     // half-width growth of the fan

function lerp(a, b, t) = a + (b - a) * t;

// ------------------------------------------------------------
// Bend: lofted morph, circle -> rounded rectangle, 90 degrees
// ------------------------------------------------------------
module sec2d(t, grow = 0) {
    // local X = vertical/height axis, local Y = width axis
    w = lerp(NOZZLE_ID, DUCT_W, t) + 2*grow;
    h = lerp(NOZZLE_ID, DUCT_H, t) + 2*grow;
    r = min(lerp(NOZZLE_ID/2, DUCT_CR, t) + grow, min(w, h)/2 - EPS);
    offset(r = r) square([max(h - 2*r, EPS), max(w - 2*r, EPS)], center = true);
}

module place_sec(u, grow) {
    a = 90 * u;
    translate([BEND_R - BEND_R*cos(a), 0, INLET_Z + BEND_R*sin(a)])
        rotate([0, a, 0])
            linear_extrude(EPS) sec2d(u, grow);
}

module bend_loft(grow = 0) {
    N = 18;
    for (i = [0 : N-1])
        hull() { place_sec(i/N, grow); place_sec((i+1)/N, grow); }
}

// ------------------------------------------------------------
// Fan: plan extrusion (curved walls) ^ side profile (sloped ceiling)
// ------------------------------------------------------------
module fan_plan(grow = 0, ext = 0) {
    NF = 16;
    x0 = BEND_R - 3;                     // overlap back into the bend
    pts = [for (i = [0 : NF]) let (s = i/NF)
              [x0 + 3 + (FAN_LEN + ext) * s, DUCT_W/2 + DWH*s*s + grow]];
    polygon(concat(
        [[x0 - grow, DUCT_W/2 + grow]],
        pts,
        [for (i = [NF : -1 : 0]) let (p = pts[i]) [p[0], -p[1]]],
        [[x0 - grow, -DUCT_W/2 - grow]]
    ));
}

module fan_side(grow = 0, ext = 0) {
    x0 = BEND_R - 3;
    x1 = X_EXIT + ext;
    slope_drop = (CEIL0_IN - CEIL1_IN) * ext / FAN_LEN;
    offset(delta = grow) polygon([
        [x0, FLOOR_IN], [x1, FLOOR_IN],
        [x1, CEIL1_IN - slope_drop], [x0, CEIL0_IN]
    ]);
}

module fan_solid(grow = 0, ext = 0) {
    intersection() {
        linear_extrude(height = 400, center = true, convexity = 4)
            fan_plan(grow, ext);
        translate([0, 200, 0]) rotate([90, 0, 0])
            linear_extrude(height = 400, convexity = 4)
                fan_side(grow, ext);
    }
}

// ------------------------------------------------------------
// Inlet stub + slip-over socket
// ------------------------------------------------------------
module stub_outer() {
    cylinder(d = max(NOZZLE_OD, NOZZLE_ID) + 2*WALL, h = INLET_Z + 1);
    // set-screw bosses, x4, kept off the y=0 split plane
    for (a = [45, 135, 225, 315]) rotate([0, 0, a]) boss();
}

module boss() {
    r_out = NOZZLE_OD/2 + WALL;
    translate([r_out - 1, -7, 2]) cube([9, 14, 15]);
}

module boss_cuts() {
    for (a = [45, 135, 225, 315]) rotate([0, 0, a]) {
        // radial M4 clearance through socket wall
        translate([NOZZLE_OD/2 - 3, 0, 9.5]) rotate([0, 90, 0])
            cylinder(d = SCREW_D, h = 20);
        // square-nut pocket, slot opens upward for drop-in nut
        translate([NOZZLE_OD/2 + WALL + 1.2, -NUT_W/2, 9.5 - NUT_W/2])
            cube([NUT_T, NUT_W, 30]);
    }
}

module stub_cavity() {
    translate([0, 0, -1]) cylinder(d = NOZZLE_OD, h = SOCKET_DEPTH + 1);
    cylinder(d = NOZZLE_ID, h = INLET_Z + 1);  // ledge = axial register
}

// ------------------------------------------------------------
// Vanes (built oversize, trimmed to the cavity by intersection)
// ------------------------------------------------------------
module cavity() {
    stub_cavity();
    bend_loft(0);
    fan_solid(0, ext = WALL + 1);
}

module bend_vane_2d(r) {
    intersection() {
        difference() { circle(r + VT/2); circle(r - VT/2); }
        // cavity spans direction angles 90..180 deg from bend center
        polygon([[0, 0], 300*[cos(85), sin(85)], [-300, 300],
                 300*[cos(185), sin(185)]]);
    }
}

module bend_vanes() {
    for (r = BEND_VANE_R)
        translate([BEND_R, 200, INLET_Z]) rotate([90, 0, 0])
            linear_extrude(height = 400, convexity = 4) bend_vane_2d(r);
}

module fan_vane_plan(y0, f) {
    NF = 12;
    xs = BEND_R + 6;                       // gap after the bend cascade
    len = X_EXIT - xs;
    pts = [for (i = [0 : NF]) let (s = i/NF)
              [xs + len*s, y0 + f*DWH*s*s]];
    polygon(concat(
        [for (p = pts) [p[0], p[1] + VT/2]],
        [for (i = [NF : -1 : 0]) let (p = pts[i]) [p[0], p[1] - VT/2]]
    ));
}

module fan_vanes() {
    n = FAN_VANES;
    for (k = [0 : n-1]) {
        f = (n == 1) ? 0 : -1 + 2*k/(n - 1);   // -1..+1 across the fan
        linear_extrude(height = 300, convexity = 4)
            fan_vane_plan(f * DUCT_W/4, f * 0.5);
    }
}

module straighteners() {
    if (STRAIGHTENERS)
        for (a = [90, 210, 330]) rotate([0, 0, a])
            translate([NOZZLE_ID/2 - 16, -VT/2, SOCKET_DEPTH + 1])
                cube([16, VT, INLET_Z - SOCKET_DEPTH + 8]);
}

module vanes_trimmed() {
    intersection() {
        cavity();
        union() { bend_vanes(); fan_vanes(); straighteners(); }
    }
}

// ------------------------------------------------------------
// Assembly and clamshell split
// ------------------------------------------------------------
module body() {
    union() {
        difference() {
            union() {
                stub_outer();
                bend_loft(WALL);
                fan_solid(WALL);
            }
            cavity();
            boss_cuts();
        }
        vanes_trimmed();
    }
}

module dowel_holes() {
    // 1.75mm filament dowel sockets, both halves, at y=0
    pts = [[-(NOZZLE_OD + WALL)/2 - 0.6, 10],
           [ (NOZZLE_OD + WALL)/2 + 0.6, 10],
           [BEND_R + FAN_LEN*0.55, FLOOR_IN - WALL/2],
           [BEND_R - 10, CEIL0_IN + WALL/2]];
    for (p = pts)
        translate([p[0], 0, p[1]]) rotate([90, 0, 0])
            cylinder(d = DOWEL_D, h = 9, center = true);
}

module half(sign) {
    difference() {
        intersection() {
            body();
            translate([-500, (sign > 0) ? 0 : -1000, -500]) cube(1000);
        }
        dowel_holes();
    }
}

if (part == 0) {
    if (show_cutaway) half(+1);
    else body();
} else if (part == 1) {
    rotate([90, 0, 0]) half(+1);    // flat split face on the bed
} else if (part == 2) {
    rotate([-90, 0, 0]) half(-1);
}
