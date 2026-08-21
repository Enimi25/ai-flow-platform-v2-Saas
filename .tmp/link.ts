import { saveConnection } from "../lib/content/connections";
import { houseCompanyId } from "../lib/workspace/store";
async function main() {
  const companyId = await houseCompanyId();
  await saveConnection({
    companyId, channel: "instagram",
    accountId: "17841400000000001", accessToken: "test-token",
    accountName: "baskinltd",
  });
  console.log("Instagram baskinltd привязан к кабинету:", companyId);
}
main();
