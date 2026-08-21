import { getSettings, saveSettings } from "../lib/settings/store";
import { houseCompanyId } from "../lib/workspace/store";
import { seedHouseWorkspace } from "../lib/workspace/seed";
async function main() {
  const id = await houseCompanyId();
  const s = await getSettings(id);
  await saveSettings({ ...s, businessDescription: "" });
  console.log("пересев:", await seedHouseWorkspace());
}
main();
