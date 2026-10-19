// SPDX-License-Identifier: MIT

// --aliases files come first: @/ resolves there when the file exists.
import { Panel } from "@components/panel";
import config from "config";
import { first } from "@/first";
// Then tsconfig paths: here @/ falls through to tsconfig's src/*.
import { user } from "@/domain/models/user";
// The longest prefix before * wins: @app/models/* over @app/*.
import { order } from "@app/models/order";
import { shell } from "@app/shell";
// Several targets: the first that finds a file.
import { client } from "~/api/client";
import { theme } from "~/theme";
// An exact key.
import { log } from "logger";
// Matches an alias but names no file, then is not a package either: unresolved as written.
import { nope } from "@/nope";

export const all = [Panel, config, first, user, order, shell, client, theme, log, nope];
