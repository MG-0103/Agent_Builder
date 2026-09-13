import Canvas from './components/canvas/Canvas';
import { useCanvasActions } from './components/canvas/hooks/useCanvasActions';
import {
  Sidebar,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarContent,
  SidebarProvider,
  SidebarTrigger,
} from './components/ui/sidebar';

export default function App() {
  const { addNode } = useCanvasActions();

  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={addNode}>
                Add Node
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarContent>
      </Sidebar>

      <main className='flex h-screen flex-1 flex-col'>
        <SidebarTrigger />
        <div className="min-h-0 flex-1">
          <Canvas />
        </div>
      </main>
    </SidebarProvider>
  )
} 