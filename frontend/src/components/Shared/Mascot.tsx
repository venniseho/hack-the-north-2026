interface MascotProps {
  state?: 'idle' | 'scanning';
  className?: string;
}

// The animation lives inside the SVGs (CSS keyframes), so a plain <img> is
// enough. Regenerate them with scripts/mascot_to_svg.py.
const SOURCES = {
  idle: '/sham-mascot.svg',
  scanning: '/sham-mascot-scanning.svg',
} as const;

export function Mascot({ state = 'idle', className }: MascotProps) {
  return <img src={SOURCES[state]} alt="" className={className} draggable={false} />;
}
