export default function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M20 2.5 35 8v11.2c0 8.6-5.8 14.5-15 18.3C10.8 33.7 5 27.8 5 19.2V8l15-5.5Z"
        fill="url(#medbalance-brand-gradient)"
      />
      <path
        d="M20 11v17M11.5 19.5h17"
        stroke="white"
        strokeWidth="4"
        strokeLinecap="round"
      />
      <circle cx="30.5" cy="10" r="2" fill="#A7F3D0" />
      <defs>
        <linearGradient id="medbalance-brand-gradient" x1="5" y1="3" x2="35" y2="38" gradientUnits="userSpaceOnUse">
          <stop stopColor="#0F766E" />
          <stop offset="1" stopColor="#14B8A6" />
        </linearGradient>
      </defs>
    </svg>
  );
}
