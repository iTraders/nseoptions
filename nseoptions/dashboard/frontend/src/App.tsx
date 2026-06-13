import { Header } from "@/components/layout/Header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StrategyBuilderPanel } from "@/features/builder/StrategyBuilderPanel";
import { OptionChainPanel } from "@/features/chain/OptionChainPanel";
import { HistoryPanel } from "@/features/history/HistoryPanel";
import { SuggestionsPanel } from "@/features/suggestions/SuggestionsPanel";
import { useChainSocket } from "@/hooks/useChainSocket";
import { useMeta } from "@/hooks/useMeta";
import { useDashboardStore, type DashboardTab } from "@/store/dashboard";

export default function App() {
  const { data: meta } = useMeta();
  const { tab, setTab, expiry } = useDashboardStore();

  const current = expiry ?? meta?.expiry ?? undefined;
  const connection = useChainSocket(current);

  return (
    <div className="min-h-screen bg-background">
      <Header meta={meta} connection={connection} />

      <main className="container py-4">
        <Tabs value={tab} onValueChange={(value) => setTab(value as DashboardTab)}>
          <TabsList>
            <TabsTrigger value="chain">Option Chain</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
            <TabsTrigger value="builder">Strategy Builder</TabsTrigger>
            <TabsTrigger value="suggestions">Suggestions</TabsTrigger>
          </TabsList>

          <TabsContent value="chain">
            <OptionChainPanel expiry={current} />
          </TabsContent>
          <TabsContent value="history">
            <HistoryPanel expiry={current} />
          </TabsContent>
          <TabsContent value="builder">
            <StrategyBuilderPanel expiry={current} />
          </TabsContent>
          <TabsContent value="suggestions">
            <SuggestionsPanel expiry={current} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
