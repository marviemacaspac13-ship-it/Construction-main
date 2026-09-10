import { supabase } from "./supabase";

export type Material = {
  id: string;
  item_id: string;
  item_name: string;
  unit: string | null;
  price: number;
  category: string;
};

export async function fetchMaterials(): Promise<Material[]> {
  const { data, error } = await supabase
    .from("materials")
    .select("id, item_id, item_name, unit, price, category")
    .order("category", { ascending: true });

  if (error) {
    throw new Error(`Failed to load materials: ${error.message}`);
  }

  return data ?? [];
}

export async function fetchMaterialsByItemId(): Promise<Record<string, Material>> {
  const list = await fetchMaterials();
  return Object.fromEntries(list.map((m) => [m.item_id, m]));
}