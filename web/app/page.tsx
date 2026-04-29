import Dashboard from "./components/Dashboard";
import ResearchOverview from "./components/ResearchOverview";
import type { ForecastBundle } from "./components/types";
import forecastsData from "../public/data/forecasts.json";

export default function Home() {
  const bundle = forecastsData as ForecastBundle;

  return (
    <main className="container">
      <ResearchOverview bundle={bundle} />
      <Dashboard bundle={bundle} />
    </main>
  );
}
