/** Version 1 contracts shared with backend/app/takeoff/contracts.py.
 * Scan saves, source-quantity recalculation and immutable editor saves are implemented.
 */
import type { Estimate } from "./estimate";
import type { FixtureReview } from './plumbing-proposals';
import type { ElectricalReview } from './electrical-proposals';

export type PlanType = "Floor Plan" | "Electrical Plan" | "Plumbing Plan";
export type PlanSource = "manual" | "detection" | "ocr" | "tags" | "cad";
export type PlumbingFixtureTag = "water_closet" | "lavatory" | "urinal" | "floor_drain" | "cleanout"
  | "kitchen_sink" | "shower" | "bathtub" | "washing_machine" | "hose_bib" | "drinking_fountain";
export type ElectricalDeviceId =
  | "GS01" | "GS02" | "GS03" | "SW01" | "SW02" | "SW03"
  | "OT01" | "OT02" | "OT03" | "ACO01" | "CLR01" | "CLR02" | "CLR03";

export type PlanSchema = {
  plan_type: PlanType;
  manual_column_count?: number | null;
  source: PlanSource;
  scale: {
    meters_per_pixel_x: number;
    meters_per_pixel_y: number;
    confirmed_by_user: boolean;
    source: "manual" | "printed_dimension" | "scale_bar" | "known_reference" | "stated_ratio";
    confidence: number;
  } | null;
  walls: {
    id: string;
    length_m: number;
    thickness: "4in" | "6in";
    height_m: number | null;
    openings: { kind: "door" | "window"; width_m: number; height_m: number; count: number }[];
  }[];
  rooms: {
    id: string;
    name: string;
    area_m2: number;
    width_m: number | null;
    length_m: number | null;
  }[];
  concrete: {
    id: string;
    kind: "footing" | "column" | "beam" | "slab";
    volume_m3: number;
    mix_class: "A" | "B" | "C";
    count: number;
    width_m: number | null;
    length_m: number | null;
    height_m: number | null;
    counted: boolean;
    slab_area_m2?: number | null;
  }[];
  concrete_basis?: PlanSchema['concrete'];
  runs: {
    id: string;
    length_m: number;
    service: "lighting" | "convenience" | "aircon" | "service_entrance" | "supply" | "drain";
    diameter: string | null;
    conductors: number;
    terminations: number;
  }[];
  fixtures: { item_id: string; count: number }[];
  fixture_tags: Record<string, number>;
  fixture_review?: FixtureReview | null;
  electrical_review?: ElectricalReview | null;
  fixture_tag_observations?: Array<{
    tag: string;
    x_px: number;
    y_px: number;
    score: number;
  }>;
};

/** Fully resolved parameters, not merely the user's partial overrides. */
export type EstimatingParams = {
  default_wall_height_m: number;
  chb_waste: number;
  mortar_waste: number;
  concrete_waste: number;
  rebar_waste: number;
  wire_waste: number;
  conduit_waste: number;
  pipe_waste: number;
  vertical_bar_spacing_m: number;
  horizontal_bar_spacing_m: number;
  rebar_item_id: string;
  slack_per_termination_m: number;
  doors_per_room: number;
  windows_per_room: number;
  include_frame: boolean;
  column_spacing_m: number;
  footing_thickness_m: number;
  slab_thickness_m: number;
  include_perimeter_beam: boolean;
  drain_branch_m_per_fixture: number;
  supply_branch_m_per_fixture: number;
  wire_m_per_device: number;
  conduit_m_per_device: number;
  lighting_route_m_per_point: number;
  lighting_conductors: number;
  box_free_conductor_m: number;
  main_run_m_per_fixture: number;
};

export type CatalogPrice = {
  item_id: string;
  item_name: string;
  unit: string | null;
  price: number;
  category: string;
  purchase_unit: {
    kind: "each" | "linear_m" | "stick" | "bag" | "volume_m3" | "mass_kg";
    stick_length_m: number | null;
  } | null;
};

export type PriceSnapshot = {
  snapshot_id: string;
  captured_at: string;
  currency: "PHP";
  items: CatalogPrice[];
};

export type EstimateInputSnapshot = {
  schema_version: 1;
  rules_version: string;
  plan: PlanSchema;
  params: EstimatingParams;
  prices: PriceSnapshot;
};

export type ScanMetadata = {
  source_sha256: string;
  pipeline_version: "image-v1";
  method: "ocr" | "tags" | "detection" | "manual";
};

/** Absolute replacements. Null/absent means no override; zero remains intentional. */
export type SourceQuantityOverrides = {
  wall_height_m?: number | null;
  slab_area_m2?: number | null;
  column_count?: number | null;
  electrical_counts?: Partial<Record<ElectricalDeviceId, number>>;
  plumbing_counts?: Partial<Record<PlumbingFixtureTag, number>>;
};

export type EstimateCorrections = {
  quantities: SourceQuantityOverrides;
  /** Absolute project prices in PHP per captured purchase unit. Omit a key to reset; zero is valid. */
  unit_prices: Record<string, number>;
  reason: string | null;
};

export type EstimateRevision = {
  id: string;
  scan_revision_id: string;
  parent_revision_id: string | null;
  created_by: string;
  created_at: string;
  corrections: EstimateCorrections;
  effective_input: EstimateInputSnapshot;
  estimate: Estimate;
};

export type RevisionSavePrecondition = {
  expected_active_revision_id: string | null;
  idempotency_key: string;
};
