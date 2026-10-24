import "./../components/toast/toast.js";
import { cloneTemplateContent, renderLucideIcons } from "./shared.js";
import {
  createDetailErrorState,
  createTicketDetailComponent,
  createTicketMessagesComponent,
  initReplyComposer,
  readJsonResponse,
} from "./conversation.js";

const ticketContainerId = document.getElementById("ticketCardSection");
const TICKET_DETAIL_API_URL = ticketContainerId?.dataset.detailUrl;

// Built from the skeleton component (<template id="tpl-detail-skeleton"> in ticket_detail.html)
function createTicketDetailSkeleton() {
  return cloneTemplateContent("tpl-detail-skeleton");
}

async function loadTicketDetail() {
  if (!ticketContainerId || !TICKET_DETAIL_API_URL) return;

  ticketContainerId.setAttribute("aria-busy", "true");
  ticketContainerId.replaceChildren(createTicketDetailSkeleton());

  try {
    const response = await fetch(TICKET_DETAIL_API_URL, {
      headers: { Accept: "application/json" },
    });

    const data = await readJsonResponse(response);
    if (!response.ok)
      throw new Error(data.error ?? `Failed to fetch ticket details (${response.status})`);

    ticketContainerId.replaceChildren(
      createTicketDetailComponent(data.ticket),
      // Reply buttons only appear when this user may actually reply
      createTicketMessagesComponent(data.messages ?? [], { canReply: data.ticket.can_reply }),
    );
  } catch (error) {
    console.error("Error loading ticket details:", error);
    ticketContainerId.replaceChildren(
      createDetailErrorState("We couldn't load this ticket.", loadTicketDetail),
    );
  } finally {
    ticketContainerId.removeAttribute("aria-busy");
    renderLucideIcons(ticketContainerId);
  }
}

loadTicketDetail();
initReplyComposer();
