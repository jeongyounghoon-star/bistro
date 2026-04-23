export interface HistoryPoint {
  date: string;
  value: number;
}

export interface ForecastPoint {
  date: string;
  median: number;
  lo: number;
  hi: number;
}

export interface SeriesForecast {
  id: string;
  title: string;
  unit: string;
  frequency: string;
  tags: string[];
  note?: string;
  forecast_start: string;
  history: HistoryPoint[];
  forecast: ForecastPoint[];
}

export interface ForecastBundle {
  generated_at: string;
  model: string;
  horizon_months: number;
  context_months: number;
  series: SeriesForecast[];
}
