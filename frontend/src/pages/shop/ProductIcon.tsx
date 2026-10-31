import { BookOpen, Camera, Coffee, Gamepad2, Gift, Headphones, Home, Laptop, Shirt, Smartphone, Sparkles, Watch, Footprints } from "lucide-react";

const MAP = {
  headphones: Headphones, watch: Watch, laptop: Laptop, camera: Camera, coffee: Coffee, home: Home, shoe: Footprints,
  shirt: Shirt, book: BookOpen, sparkles: Sparkles, gift: Gift, gamepad: Gamepad2, phone: Smartphone,
} as const;

const HUES: Record<string, string> = {
  headphones: "from-cyan-500/30", watch: "from-sky-500/30", laptop: "from-indigo-500/30", camera: "from-teal-500/30",
  coffee: "from-amber-600/30", home: "from-orange-400/25", shoe: "from-emerald-500/30", shirt: "from-blue-500/30",
  book: "from-yellow-500/25", sparkles: "from-pink-500/25", gift: "from-fuchsia-500/30", gamepad: "from-violet-500/30",
  phone: "from-slate-400/30",
};

export default function ProductIcon({ image, className = "h-40" }: { image: string; className?: string }) {
  const I = MAP[image as keyof typeof MAP] ?? Sparkles;
  return (
    <div className={`relative flex items-center justify-center overflow-hidden rounded-lg bg-gradient-to-br ${HUES[image] ?? "from-cyan-500/20"} to-ink-900 ${className}`}>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(255,255,255,.08),transparent_50%)]" />
      <I className="h-1/3 w-1/3 text-fog-100/90" strokeWidth={1.4} />
    </div>
  );
}
