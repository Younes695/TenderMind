import { Link } from "react-router-dom";
import logo from "../assets/logo.jpg";

function Header() {
  return (
    <header className="w-full border-b border-white/10 bg-[#102542]">
      <div className="mx-auto flex h-[58px] max-w-[1190px] items-center justify-between px-4 sm:px-6 lg:px-8">

        {/* Logo */}
        <Link to="/" className="flex shrink-0 items-center gap-2">
          <img
            src={logo}
            alt="TenderMind logo"
            className="h-8 w-8 rounded-md object-cover"
          />

          <span className="text-base font-bold text-white sm:text-lg">
            TENDER<span className="text-[#C8A96B]">MIND</span>
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="ml-auto mr-8 hidden items-center gap-5 lg:flex xl:mr-12 xl:gap-7">
          <Link
            to="/product"
            className="text-sm font-semibold text-white transition-colors hover:text-[#C8A96B]"
          >
            Product
          </Link>

          <Link
            to="/solutions"
            className="text-sm font-semibold text-white transition-colors hover:text-[#C8A96B]"
          >
            Solutions
          </Link>

          <Link
            to="/industries"
            className="text-sm font-semibold text-white transition-colors hover:text-[#C8A96B]"
          >
            Industries
          </Link>

          <Link
            to="/how-it-works"
            className="text-sm font-semibold text-white transition-colors hover:text-[#C8A96B]"
          >
            How It Works
          </Link>

          <Link
            to="/security"
            className="text-sm font-semibold text-white transition-colors hover:text-[#C8A96B]"
          >
            Security
          </Link>

          <Link
            to="/pricing"
            className="text-sm font-semibold text-white transition-colors hover:text-[#C8A96B]"
          >
            Pricing
          </Link>
        </nav>

        {/* Desktop Actions */}
        <div className="hidden items-center gap-5 lg:flex">
          <Link
            to="/login"
            className="text-sm font-medium text-[#D7B15F] transition-colors hover:text-white"
          >
            Log in
          </Link>

          <Link
            to="/demo"
            className="rounded-md bg-[#D7B15F] px-4 py-2 text-xs font-semibold text-[#102542] transition-colors hover:bg-[#F7D387]"
          >
            Book a Demo
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          type="button"
          className="flex h-9 w-9 items-center justify-center rounded-md border border-white/20 text-white transition-colors hover:bg-white/10 lg:hidden"
          aria-label="Open menu"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth="2"
            stroke="currentColor"
            className="h-5 w-5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>

      </div>
    </header>
  );
}

export default Header;