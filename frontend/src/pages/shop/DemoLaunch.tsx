import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ErrorBox, Loading } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { setDemoContext, useCart, type Product } from "../../lib/cart";

interface Preset {
  key: string; title: string; shopper_email: string; device_fingerprint: string; geo: { lat: number; lon: number } | null;
  products: { product_id: string; quantity: number }[];
}

/** Prepares the shopper-side context for a demo scenario (persona, device, cart) and hands off to PayPal checkout. */
export default function DemoLaunch() {
  const { key } = useParams();
  const { user, logout } = useAuth();
  const { replaceWith } = useCart();
  const nav = useNavigate();
  const [err, setErr] = useState<unknown>(null);
  const presets = useQuery({ queryKey: ["demo-presets"], queryFn: () => api<Preset[]>("/api/shop/demo-presets") });
  const products = useQuery({ queryKey: ["products"], queryFn: () => api<Product[]>("/api/shop/products") });

  useEffect(() => {
    if (!presets.data || !products.data) return;
    const p = presets.data.find((x) => x.key === key?.toUpperCase());
    if (!p) { setErr(new Error("Unknown scenario")); return; }
    const fp = p.device_fingerprint === "NEW" ? `fp-demo-new-device-${Math.random().toString(36).slice(2, 10)}` : p.device_fingerprint;
    setDemoContext(fp, p.geo);
    replaceWith(p.products.map((l) => ({ product: products.data!.find((x) => x.id === l.product_id)!, quantity: l.quantity })));
    if (user?.email === p.shopper_email) nav("/shop/checkout", { replace: true });
    else {
      if (user) logout();
      nav(`/login?email=${encodeURIComponent(p.shopper_email)}&next=/shop/checkout`, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presets.data, products.data]);

  const failure = err || presets.error || products.error;
  return failure ? <ErrorBox error={failure} /> : <Loading label="Preparing demo checkout" />;
}
