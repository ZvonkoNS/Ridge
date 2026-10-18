// Recorded job parameters as text, exactly as signed in the report.

/** A recorded parameter value as text: none, a scalar, or compact JSON for lists and objects. */
export function parameterText(value: unknown): string {
  if (value === null || value === undefined) {
    return "none";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

/** Every recorded parameter, exactly as signed. */
export function ParameterList({ parameters }: { parameters: Record<string, unknown> }) {
  return (
    <ul className="paramlist">
      {Object.entries(parameters).map(([key, value]) => (
        <li key={key}>
          <span className="paramlist-key">{key}</span> <code>{parameterText(value)}</code>
        </li>
      ))}
    </ul>
  );
}
