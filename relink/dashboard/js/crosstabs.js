/**
 * PDL Cross-tabs bar charts.
 */
import { makeBarChart } from './charts.js';

export function render(chartData) {
    makeBarChart('chart-manip', chartData['Manipulation'], false);
    makeBarChart('chart-abstr', chartData['Abstraction'], false);
    makeBarChart('chart-know', chartData['Knowledge'], false);
    makeBarChart('chart-domain', chartData['Knowledge Domain'], true);
}
