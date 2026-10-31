import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import ConsoleLayout from "./layouts/ConsoleLayout";
import ShopLayout from "./layouts/ShopLayout";
import { AuthProvider } from "./lib/auth";
import { CartProvider } from "./lib/cart";
import { LiveProvider } from "./lib/live";
import AuditCentre from "./pages/console/AuditCentre";
import CommandCentre from "./pages/console/CommandCentre";
import FraudIntelligence from "./pages/console/FraudIntelligence";
import Investigations from "./pages/console/Investigations";
import InvestigationWorkspace from "./pages/console/InvestigationWorkspace";
import LiveTransactions from "./pages/console/LiveTransactions";
import ModelAnalytics from "./pages/console/ModelAnalytics";
import NetworkGraph from "./pages/console/NetworkGraph";
import PayPalPayments from "./pages/console/PayPalPayments";
import Settings from "./pages/console/Settings";
import Login from "./pages/Login";
import Cart from "./pages/shop/Cart";
import Catalog from "./pages/shop/Catalog";
import Checkout from "./pages/shop/Checkout";
import DemoLaunch from "./pages/shop/DemoLaunch";
import Orders from "./pages/shop/Orders";
import ProductDetail from "./pages/shop/ProductDetail";

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 5_000, refetchOnWindowFocus: false, retry: 1 } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <LiveProvider>
          <CartProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/shop" element={<ShopLayout />}>
                  <Route index element={<Catalog />} />
                  <Route path="product/:id" element={<ProductDetail />} />
                  <Route path="cart" element={<Cart />} />
                  <Route path="checkout" element={<Checkout />} />
                  <Route path="orders" element={<Orders />} />
                  <Route path="demo/:key" element={<DemoLaunch />} />
                </Route>
                <Route path="/console" element={<ConsoleLayout />}>
                  <Route index element={<CommandCentre />} />
                  <Route path="transactions" element={<LiveTransactions />} />
                  <Route path="intelligence" element={<FraudIntelligence />} />
                  <Route path="network" element={<NetworkGraph />} />
                  <Route path="investigations" element={<Investigations />} />
                  <Route path="investigate/:txnId" element={<InvestigationWorkspace />} />
                  <Route path="payments" element={<PayPalPayments />} />
                  <Route path="models" element={<ModelAnalytics />} />
                  <Route path="audit" element={<AuditCentre />} />
                  <Route path="settings" element={<Settings />} />
                </Route>
                <Route path="*" element={<Navigate to="/shop" replace />} />
              </Routes>
            </BrowserRouter>
          </CartProvider>
        </LiveProvider>
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
