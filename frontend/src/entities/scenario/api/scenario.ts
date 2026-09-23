import { apiRequest } from "@/shared/api";
import { scenarioInputSchema, scenarioPreviewSchema, type ScenarioInput } from "../model/schema";
export function previewScenario(input: ScenarioInput) {
  const values = scenarioInputSchema.parse(input);
  return apiRequest("/api/v1/scenarios/preview", scenarioPreviewSchema, { method: "POST", body: JSON.stringify({ ...values, growth_multiplier: String(values.growth_multiplier), service_level: String(values.service_level), budget_limit: values.budget_limit === null ? null : String(values.budget_limit) }) });
}
