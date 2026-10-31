import { LogIn, LogOut, Package, ShieldCheck, ShoppingCart } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { isStaff, useAuth } from "../lib/auth";
import { useCart } from "../lib/cart";

export default function ShopLayout() {
  const { user, logout } = useAuth();
  const { count } = useCart();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-ink-700/70 bg-ink-950/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <Link to="/shop" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-sky-600 text-ink-950">
              <ShieldCheck className="h-4.5 w-4.5" style={{ width: 18, height: 18 }} />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold tracking-wide">SENTINEL MERCHANT</div>
              <div className="text-[10px] uppercase tracking-[0.14em] text-fog-400">Demo marketplace · protected by Sentinel</div>
            </div>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <NavLink to="/shop" end className={({ isActive }) => `rounded-md px-3 py-1.5 ${isActive ? "text-cyan-300" : "text-fog-300 hover:text-fog-100"}`}>Shop</NavLink>
            {user?.role === "CUSTOMER" && (
              <NavLink to="/shop/orders" className={({ isActive }) => `flex items-center gap-1.5 rounded-md px-3 py-1.5 ${isActive ? "text-cyan-300" : "text-fog-300 hover:text-fog-100"}`}>
                <Package className="h-4 w-4" /> <span className="hidden sm:inline">Orders</span>
              </NavLink>
            )}
            <NavLink to="/shop/cart" className="relative flex items-center gap-1.5 rounded-md px-3 py-1.5 text-fog-300 hover:text-fog-100">
              <ShoppingCart className="h-4 w-4" />
              {count > 0 && <span className="absolute -right-0.5 -top-0.5 rounded-full bg-cyan-400 px-1.5 text-[10px] font-bold text-ink-950">{count}</span>}
            </NavLink>
            {isStaff(user) && <Link to="/console" className="btn-ghost ml-1 py-1.5 text-xs">Console</Link>}
            {user ? (
              <button onClick={logout} className="ml-1 flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs text-fog-400 hover:text-fog-100" title="Sign out">
                <span className="hidden sm:inline">{user.full_name}</span><LogOut className="h-4 w-4" />
              </button>
            ) : (
              <Link to="/login?next=/shop" className="btn-ghost ml-1 py-1.5 text-xs"><LogIn className="h-3.5 w-3.5" />Sign in</Link>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8"><Outlet /></main>
      <footer className="border-t border-ink-700/60 py-6 text-center text-xs text-fog-500">
        Demo storefront with synthetic products. Payments run on PayPal Sandbox — no real money moves.
      </footer>
    </div>
  );
}
