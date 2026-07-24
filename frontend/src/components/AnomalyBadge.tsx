export function AnomalyBadge({ detected, details }: { detected: boolean; details: string | null }) {
  if (!detected) return null;
  return (
    <span
      title={details ?? "Anomalie détectée"}
      className="inline-block px-2 py-0.5 rounded text-xs bg-orange-100 text-orange-700 cursor-help"
    >
      ⚠ à vérifier
    </span>
  );
}