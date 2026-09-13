import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuTrigger,
} from '../../../ui/context-menu'

import {
    Dialog,
    DialogContent, 
    DialogHeader, 
    DialogTitle, 
    DialogFooter,
} from '../../../ui/dialog'

import { Input } from '../../../ui/input'
import { Button } from '../../../ui/button'

import { useCanvasActions } from '../../hooks/useCanvasActions';
import { useState } from 'react';


type NodeContextMenuProps = {
    nodeId: string,
    children: React.ReactNode;
}

export function NodeContextMenu({
    nodeId, 
    children, 
}: NodeContextMenuProps) {
    const { 
        removeNode, 
        renameNode, 
        duplicateNode 
    } = useCanvasActions();

    const [renameOpen, setRenameOpen] = useState(false);
    const [newName, setNewName] = useState('');

    const handleRename = () => {
        const name = newName.trim();

        if(!name) return;

        renameNode(nodeId, name);

        setRenameOpen(false);
        setNewName('');
    }
    
    return (
        <>
            <ContextMenu>
                <ContextMenuTrigger>
                    { children }
                </ContextMenuTrigger>

                <ContextMenuContent>
                    <ContextMenuItem 
                        onClick={() => removeNode(nodeId)}
                    >
                        Delete
                    </ContextMenuItem>

                    <ContextMenuItem
                        onClick={() => {
                            setNewName('');
                            setRenameOpen(true);
                        }}
                    >
                        Rename
                    </ContextMenuItem>

                    <ContextMenuItem
                        onClick={() => duplicateNode(nodeId)}
                    >
                        Duplicate
                    </ContextMenuItem>
                </ContextMenuContent>
            </ContextMenu>

            <Dialog
                open={renameOpen}
                onOpenChange={setRenameOpen}    
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>
                            Rename node
                        </DialogTitle>
                    </DialogHeader>

                    <Input 
                        value={newName}
                        onChange={(event) => 
                            setNewName(event.target.value)
                        }
                        placeholder="Node name"
                        onKeyDown={(event) => {
                            if (event.key === "Enter") {
                                handleRename();
                            }
                        }}
                    />
                    
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setRenameOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleRename}
                        >
                            Rename
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    )
}