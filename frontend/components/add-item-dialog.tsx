'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X, Loader2, CheckCircle2, AlertCircle, Image as ImageIcon } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { TypeSelector } from '@/components/type-selector';
import { useCreateItem, useBulkCreateItems, BulkUploadResponse } from '@/lib/hooks/use-items';
import { useFamily } from '@/lib/hooks/use-family';
import { CLOTHING_COLORS } from '@/lib/types';
import { useTranslations } from 'next-intl';

interface AddItemDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface FileWithPreview {
  file: File;
  preview: string;
  id: string;
}

// Sentinel for "assign to me" in the owner Select (Radix Select can't use an empty-string value)
const ME_VALUE = '__me__';

export function AddItemDialog({ open, onOpenChange }: AddItemDialogProps) {
  const t = useTranslations('wardrobe.addItem');
  const tc = useTranslations('common');
  // Single upload state
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [type, setType] = useState('');
  const [subtype, setSubtype] = useState('');
  const [name, setName] = useState('');
  const [brand, setBrand] = useState('');
  const [primaryColor, setPrimaryColor] = useState('');
  const [notes, setNotes] = useState('');
  const [ownerUserId, setOwnerUserId] = useState(ME_VALUE);
  const [isPrivate, setIsPrivate] = useState(false);

  // Bulk upload state
  const [bulkFiles, setBulkFiles] = useState<FileWithPreview[]>([]);
  const [bulkResult, setBulkResult] = useState<BulkUploadResponse | null>(null);
  const [skipAi, setSkipAi] = useState(false);
  const [activeTab, setActiveTab] = useState('single');
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);

  // Track blob URLs for cleanup on unmount
  const blobUrlsRef = useRef<Set<string>>(new Set());

  const createItem = useCreateItem();
  const bulkCreateItems = useBulkCreateItems();
  const { data: family } = useFamily();
  const familyMembers = family?.members ?? [];
  const showOwnerSelect = familyMembers.length > 1;

  // Cleanup blob URLs on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      blobUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      blobUrlsRef.current.clear();
    };
  }, []);

  // Single file drop handler
  const onDropSingle = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      setFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  }, []);

  // Bulk file drop handler
  const onDropBulk = useCallback((acceptedFiles: File[]) => {
    const newFiles: FileWithPreview[] = acceptedFiles.map((file) => {
      const preview = URL.createObjectURL(file);
      blobUrlsRef.current.add(preview);
      return {
        file,
        preview,
        id: `${file.name}-${Date.now()}-${Math.random()}`,
      };
    });
    setBulkFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const { getRootProps: getSingleRootProps, getInputProps: getSingleInputProps, isDragActive: isSingleDragActive } = useDropzone({
    onDrop: onDropSingle,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.webp', '.heic', '.heif'],
    },
    maxFiles: 1,
    multiple: false,
  });

  const { getRootProps: getBulkRootProps, getInputProps: getBulkInputProps, isDragActive: isBulkDragActive } = useDropzone({
    onDrop: onDropBulk,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.webp', '.heic', '.heif'],
    },
    multiple: true,
  });

  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!file) return;

    const formData = new FormData();
    formData.append('image', file);
    // Type is optional - AI will detect if not provided
    if (type) formData.append('type', type);
    if (subtype) formData.append('subtype', subtype);
    if (name) formData.append('name', name);
    if (brand) formData.append('brand', brand);
    if (primaryColor) formData.append('primary_color', primaryColor);
    if (notes) formData.append('notes', notes);
    if (showOwnerSelect && ownerUserId !== ME_VALUE) formData.append('owner_user_id', ownerUserId);
    if (isPrivate) formData.append('is_private', 'true');

    try {
      await createItem.mutateAsync(formData);
      handleClose();
    } catch (error) {
      console.error('Failed to create item:', error);
    }
  };

  const handleBulkSubmit = async () => {
    if (bulkFiles.length === 0) return;

    try {
      const result = await bulkCreateItems.mutateAsync({
        files: bulkFiles.map((f) => f.file),
        skipAi,
      });
      setBulkResult(result);

      // Show toast based on results
      if (result.failed === 0) {
        toast.success(t('bulk.allSuccess', { count: result.successful }));
      } else if (result.successful === 0) {
        toast.error(t('bulk.allFailed', { count: result.failed }));
      } else {
        toast.warning(t('bulk.partial', { success: result.successful, failed: result.failed }));
      }
    } catch (error) {
      console.error('Failed to bulk upload:', error);
      toast.error(t('bulk.uploadError'));
    }
  };

  // Check if there are unsaved files that would be lost on close
  const hasUnsavedFiles = (file !== null) || (bulkFiles.length > 0 && !bulkResult);

  const handleCloseRequest = () => {
    // Show confirmation if there are unsaved files and not currently uploading
    if (hasUnsavedFiles && !createItem.isPending && !bulkCreateItems.isPending) {
      setShowCloseConfirm(true);
    } else {
      handleClose();
    }
  };

  const handleClose = () => {
    // Single upload cleanup
    setFile(null);
    setPreview(null);
    setType('');
    setSubtype('');
    setName('');
    setBrand('');
    setPrimaryColor('');
    setNotes('');
    setOwnerUserId(ME_VALUE);
    setIsPrivate(false);

    // Bulk upload cleanup - also clean up from the ref
    bulkFiles.forEach((f) => {
      URL.revokeObjectURL(f.preview);
      blobUrlsRef.current.delete(f.preview);
    });
    setBulkFiles([]);
    setBulkResult(null);
    setSkipAi(false);
    setActiveTab('single');
    setShowCloseConfirm(false);

    onOpenChange(false);
  };

  const clearSingleFile = () => {
    setFile(null);
    setPreview(null);
  };

  const removeBulkFile = (id: string) => {
    setBulkFiles((prev) => {
      const fileToRemove = prev.find((f) => f.id === id);
      if (fileToRemove) {
        URL.revokeObjectURL(fileToRemove.preview);
        blobUrlsRef.current.delete(fileToRemove.preview);
      }
      return prev.filter((f) => f.id !== id);
    });
  };

  const clearBulkFiles = () => {
    bulkFiles.forEach((f) => {
      URL.revokeObjectURL(f.preview);
      blobUrlsRef.current.delete(f.preview);
    });
    setBulkFiles([]);
    setBulkResult(null);
    setSkipAi(false);
  };

  return (
    <>
    <Dialog open={open} onOpenChange={handleCloseRequest}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('title')}</DialogTitle>
          <DialogDescription>
            {t('subtitle')}
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="single">{t('singleItem')}</TabsTrigger>
            <TabsTrigger value="bulk">{t('bulkUpload')}</TabsTrigger>
          </TabsList>

          {/* Single Item Upload */}
          <TabsContent value="single" className="space-y-4">
            <form onSubmit={handleSingleSubmit} className="space-y-4">
              {!preview ? (
                <div
                  {...getSingleRootProps()}
                  className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                    isSingleDragActive
                      ? 'border-primary bg-primary/5'
                      : 'border-muted-foreground/25 hover:border-primary/50'
                  }`}
                >
                  <input {...getSingleInputProps()} />
                  <Upload className="mx-auto h-12 w-12 text-muted-foreground" />
                  <p className="mt-2 text-sm text-muted-foreground">
                    {isSingleDragActive
                      ? t('dropzoneActive')
                      : t('dropzone')}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t('formatHint')}
                  </p>
                </div>
              ) : (
                <div className="relative">
                  <img
                    src={preview}
                    alt={t('previewAlt')}
                    className="w-full h-48 object-cover rounded-lg"
                  />
                  <Button
                    type="button"
                    variant="destructive"
                    size="icon"
                    className="absolute top-2 right-2 h-8 w-8"
                    onClick={clearSingleFile}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}

              <div className="space-y-3">
                <TypeSelector
                  value={{ type: type || undefined, subtype: subtype || undefined }}
                  onChange={(v) => {
                    setType(v.type ?? '');
                    setSubtype(v.subtype ?? '');
                  }}
                />

                <div className="space-y-2">
                  <Label htmlFor="name">{t('namePlaceholder')}</Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={t('nameInputPlaceholder')}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="brand">{t('brandPlaceholder')}</Label>
                    <Input
                      id="brand"
                      value={brand}
                      onChange={(e) => setBrand(e.target.value)}
                      placeholder={t('brandInputPlaceholder')}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="color">{t('primaryColor')}</Label>
                    <Select value={primaryColor} onValueChange={setPrimaryColor}>
                      <SelectTrigger>
                        <SelectValue placeholder={t('selectPlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {CLOTHING_COLORS.map((c) => (
                          <SelectItem key={c.value} value={c.value}>
                            <div className="flex items-center gap-2">
                              <div
                                className="w-3 h-3 rounded-full border"
                                style={{ backgroundColor: c.hex }}
                              />
                              {c.name}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="notes">{t('notesPlaceholder')}</Label>
                  <Input
                    id="notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder={t('notesInputPlaceholder')}
                  />
                </div>

                {showOwnerSelect && (
                  <div className="space-y-2">
                    <Label htmlFor="owner">Owner</Label>
                    <Select value={ownerUserId} onValueChange={setOwnerUserId}>
                      <SelectTrigger id="owner">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={ME_VALUE}>Me</SelectItem>
                        {familyMembers.map((member) => (
                          <SelectItem key={member.id} value={member.id}>
                            {member.display_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                <div className="flex items-center justify-between p-3 border rounded-lg bg-muted/50">
                  <div className="space-y-0.5">
                    <Label htmlFor="is-private">Private</Label>
                    <p className="text-xs text-muted-foreground">
                      Only visible to you, hidden from family members
                    </p>
                  </div>
                  <Switch id="is-private" checked={isPrivate} onCheckedChange={setIsPrivate} />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={handleCloseRequest}>
                  {tc('cancel')}
                </Button>
                <Button
                  type="submit"
                  disabled={!file || createItem.isPending}
                >
                  {createItem.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('uploading')}
                    </>
                  ) : (
                    t('submit')
                  )}
                </Button>
              </div>
            </form>
          </TabsContent>

          {/* Bulk Upload */}
          <TabsContent value="bulk" className="space-y-4">
            {!bulkResult ? (
              <>
                <div
                  {...getBulkRootProps()}
                  className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                    isBulkDragActive
                      ? 'border-primary bg-primary/5'
                      : 'border-muted-foreground/25 hover:border-primary/50'
                  }`}
                >
                  <input {...getBulkInputProps()} />
                  <Upload className="mx-auto h-10 w-10 text-muted-foreground" />
                  <p className="mt-2 text-sm text-muted-foreground">
                    {isBulkDragActive
                      ? t('dropzoneActive')
                      : t('dropzone')}
                  </p>
                </div>

                {bulkFiles.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium">
                        {t('bulk.imageCount', { count: bulkFiles.length })}
                      </p>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={clearBulkFiles}
                      >
                        {t('bulk.clearAll')}
                      </Button>
                    </div>

                    <ScrollArea className="h-[200px] rounded-md border p-2">
                      <div className="grid grid-cols-4 gap-2">
                        {bulkFiles.map((f) => (
                          <div key={f.id} className="relative group">
                            <img
                              src={f.preview}
                              alt={f.file.name}
                              className="w-full aspect-square object-cover rounded-md"
                            />
                            <Button
                              type="button"
                              variant="destructive"
                              size="icon"
                              className="absolute top-1 right-1 h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={() => removeBulkFile(f.id)}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                            <p className="text-[10px] text-muted-foreground truncate mt-1 px-1">
                              {f.file.name}
                            </p>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>

                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="skip-ai"
                        checked={skipAi}
                        onCheckedChange={(checked) => setSkipAi(checked === true)}
                      />
                      <Label htmlFor="skip-ai" className="text-xs font-normal text-muted-foreground">
                        {t('bulk.skipAi')}
                      </Label>
                    </div>
                    {!skipAi && (
                      <p className="text-xs text-muted-foreground">
                        {t('bulk.hint')}
                      </p>
                    )}
                  </div>
                )}

                {bulkCreateItems.isPending && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm">{t('bulk.uploadingCount', { count: bulkFiles.length })}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">{bulkCreateItems.uploadProgress}%</span>
                    </div>
                    <Progress value={bulkCreateItems.uploadProgress} className="h-2" />
                  </div>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" variant="outline" onClick={handleCloseRequest}>
                    {tc('cancel')}
                  </Button>
                  <Button
                    onClick={handleBulkSubmit}
                    disabled={bulkFiles.length === 0 || bulkCreateItems.isPending}
                  >
                    {bulkCreateItems.isPending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {t('uploading')}
                      </>
                    ) : (
                      <>
                        <Upload className="mr-2 h-4 w-4" />
                        {t('bulk.uploadButton', { count: bulkFiles.length })}
                      </>
                    )}
                  </Button>
                </div>
              </>
            ) : (
              /* Bulk Upload Results */
              <div className="space-y-4">
                <div className="flex items-center justify-center gap-3 py-4">
                  {bulkResult.failed === 0 ? (
                    <CheckCircle2 className="h-12 w-12 text-green-500" />
                  ) : bulkResult.successful === 0 ? (
                    <AlertCircle className="h-12 w-12 text-destructive" />
                  ) : (
                    <AlertCircle className="h-12 w-12 text-yellow-500" />
                  )}
                </div>

                <div className="text-center">
                  <p className="text-lg font-medium">
                    {t('bulk.resultSuccess', { success: bulkResult.successful, total: bulkResult.total })}
                  </p>
                  {bulkResult.failed > 0 && (
                    <p className="text-sm text-muted-foreground">
                      {t('bulk.resultFailed', { count: bulkResult.failed })}
                    </p>
                  )}
                </div>

                <ScrollArea className="h-[200px] rounded-md border">
                  <div className="p-3 space-y-2">
                    {bulkResult.results.map((result, index) => (
                      <div
                        key={index}
                        className={`flex items-center gap-3 p-2 rounded-md ${
                          result.success ? 'bg-green-500/10' : 'bg-destructive/10'
                        }`}
                      >
                        {result.success ? (
                          <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{result.filename}</p>
                          {result.error && (
                            <p className="text-xs text-destructive">{result.error}</p>
                          )}
                        </div>
                        {result.item && (
                          <ImageIcon className="h-4 w-4 text-muted-foreground shrink-0" />
                        )}
                      </div>
                    ))}
                  </div>
                </ScrollArea>

                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="outline" onClick={clearBulkFiles}>
                    {t('bulk.uploadMore')}
                  </Button>
                  <Button onClick={handleClose}>
                    {tc('done')}
                  </Button>
                </div>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>

    <AlertDialog open={showCloseConfirm} onOpenChange={setShowCloseConfirm}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('bulk.discardConfirm.title')}</AlertDialogTitle>
          <AlertDialogDescription>
            {activeTab === 'single'
              ? t('bulk.discardConfirm.singleImage')
              : t('bulk.discardConfirm.imageCount', { count: bulkFiles.length })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t('bulk.discardConfirm.keepEditing')}</AlertDialogCancel>
          <AlertDialogAction onClick={handleClose}>{t('bulk.discardConfirm.discard')}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  );
}
