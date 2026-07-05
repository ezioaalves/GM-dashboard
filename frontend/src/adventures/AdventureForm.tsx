export default function AdventureForm({ onBack }: { adventureId: number; onBack: () => void }) {
  return <button onClick={onBack}>Back</button>;
}
