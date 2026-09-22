import { Config } from "@remotion/cli/config";

/**
 * Кэш кадров OffthreadVideo Remotion подбирает по объёму оперативной памяти.
 * На машине с 64 ГБ он вырастает до нескольких гигабайт, Windows расширяет под это
 * файл подкачки на диске C — и свободное место там падает до нуля, после чего
 * Chrome перестаёт отдавать кадры («Could not extract frame from compositor»).
 * Ограничиваем кэш явно: на композиции со скринкастом этого достаточно.
 */
Config.setOffthreadVideoCacheSizeInBytes(1_000_000_000);
