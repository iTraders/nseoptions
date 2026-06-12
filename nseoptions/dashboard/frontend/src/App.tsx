import { Header } from "@/components/layout/Header";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OptionChainPanel } from "@/features/chain/OptionChainPanel";
import { useChainSocket } from "@/hooks/useChainSocket";
import { useMeta } from "@/hooks/useMeta";
import { useDashboardStore, type DashboardTab } from "@/store/dashboard";

function Placeholder({ title }: { title: string }) {
  return (
    <Card>
      <CardContent className="flex h-72 items-center justify-center text-sm text-muted-foreground">
        {title}
      </CardContent>
    </Card>
  );
}

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
            <Placeholder title="Per-strike price / OI / IV history" />
          </TabsContent>
          <TabsContent value="builder">
            <Placeholder title="Multi-leg strategy builder" />
          </TabsContent>
          <TabsContent value="suggestions">
            <Placeholder title="Rules-based strategy suggestions" />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
