/**
 * Readability guidance shown on both upload entry points (the Upload screen and
 * the new-project modal), so a user gets the same advice whichever way they come.
 *
 * Advice, not a threshold: downsampling measurably loses reads, but no minimum
 * pixel count holds for every plan type (supabase/PLAN_ASSET_DEPLOYMENT.md).
 */
export const ORIGINAL_EXPORT_TIP =
  "Upload the original export. Enlarging a small screenshot does not restore missing detail.";

const TIPS: Record<string, string[]> = {
  "Floor Plan": [
    "Printed room dimensions should be sharp and legible, not blurry.",
    "Upload the sheet flat and square-on — avoid skewed or angled photos.",
  ],
  "Electrical Plan": [
    "Keep device symbols and nearby labels clear enough to review.",
    "Keep the legend visible if the sheet includes one.",
  ],
  "Plumbing Plan": [
    "Fixture tags (WC, LAV, FD) need to be readable, not just visible.",
    "Make sure tag callouts aren't cropped at the sheet edge.",
  ],
};

export function uploadTips(planType: string): string[] {
  return [...(TIPS[planType] ?? []), ORIGINAL_EXPORT_TIP];
}
